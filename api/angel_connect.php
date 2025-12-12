<?php
/**
 * /project/api/angel_connect.php
 *
 * Secure SmartAPI (Angel One) connect endpoint.
 * - Reads configuration from api/config.php (which in turn reads env)
 * - Verifies PIN (DASHBOARD_PIN)
 * - Performs loginByPassword to SmartAPI using TOTP
 * - Writes session file atomically outside webroot
 *
 * Usage: POST JSON { "clientcode": "S2105830", "pin": "1600" }
 *
 * Important:
 * - Ensure api/config.php returns keys used below (base_auth_url, api_key, totp_secret, session_file, pin)
 * - Require PHP cURL and ext-json.
 */

declare(strict_types=1);
date_default_timezone_set('Asia/Kolkata');

header('Content-Type: application/json; charset=utf-8');
header('Access-Control-Allow-Origin: ' . (getenv('APP_DOMAIN') ?: '*'));
header('Access-Control-Allow-Methods: POST, OPTIONS');
header('Access-Control-Allow-Headers: Content-Type');

if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') {
    exit; // CORS preflight
}

require_once __DIR__ . '/config.php';
require_once __DIR__ . '/GoogleAuthenticator.php'; // keep existing PHPGangsta class or vendor equivalent
use PHPGangsta_GoogleAuthenticator;

function send_json(array $data, int $code = 200): void {
    http_response_code($code);
    echo json_encode($data, JSON_UNESCAPED_UNICODE);
    exit;
}

/**
 * Atomic JSON file write (temp + rename)
 * throws Exception on failure
 */
function safe_write_json_file(string $path, $data): bool {
    $dir = dirname($path);
    if (!is_dir($dir)) {
        throw new Exception("Directory does not exist: {$dir}");
    }
    // security: ensure session path is outside api/webroot
    $realDir = realpath($dir);
    $apiDir = realpath(__DIR__);
    if ($realDir !== false && $apiDir !== false && strpos($realDir, $apiDir) === 0) {
        throw new Exception("Refusing to write session file inside webroot. Use storage path outside webroot.");
    }
    if (!is_writable($dir)) {
        throw new Exception("Directory not writable: {$dir}");
    }
    $tmp = tempnam($dir, 'sess_');
    if ($tmp === false) {
        throw new Exception("Cannot create temp file in {$dir}");
    }
    $ok = file_put_contents($tmp, json_encode($data, JSON_UNESCAPED_UNICODE | JSON_PRETTY_PRINT));
    if ($ok === false) {
        @unlink($tmp);
        throw new Exception("Failed to write temp session file");
    }
    @chmod($tmp, 0640);
    if (!@rename($tmp, $path)) {
        @unlink($tmp);
        throw new Exception("Failed to rename temp session file to {$path}");
    }
    return true;
}

/** Helper: simple POST JSON using cURL */
function http_post_json(string $url, array $headers, array $bodyArr, int $timeout = 20): array {
    $ch = curl_init($url);
    $payload = json_encode($bodyArr);
    $headerLines = [];
    foreach ($headers as $k => $v) $headerLines[] = $k . ': ' . $v;
    $headerLines[] = 'Content-Type: application/json';
    $headerLines[] = 'Accept: application/json';
    curl_setopt_array($ch, [
        CURLOPT_POST => true,
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_HTTPHEADER => $headerLines,
        CURLOPT_POSTFIELDS => $payload,
        CURLOPT_TIMEOUT => $timeout,
    ]);
    $resBody = curl_exec($ch);
    $err = curl_error($ch);
    $status = curl_getinfo($ch, CURLINFO_HTTP_CODE);
    curl_close($ch);
    if ($err) {
        throw new Exception("cURL error: ".$err);
    }
    $json = json_decode($resBody, true);
    return [$status, $json, $resBody];
}

try {
    $raw = file_get_contents('php://input');
    $body = json_decode($raw, true) ?: [];
    $clientcode_input = strtoupper(trim($body['clientcode'] ?? ''));
    $pin_input = trim($body['pin'] ?? '');

    if ($clientcode_input === '' || $pin_input === '') {
        send_json(['status' => 'error', 'message' => 'Clientcode and PIN are required.'], 400);
    }

    // read config (env-driven)
    $config = require __DIR__ . '/config.php';

    $backendPin = (string)($config['DASHBOARD_PIN'] ?? $config['pin'] ?? '');
    if ($backendPin === '' || $pin_input !== $backendPin) {
        send_json(['status' => 'error', 'message' => 'Invalid dashboard PIN.'], 403);
    }

    $base = rtrim($config['SMARTAPI_BASE'] ?? ($config['base_auth_url'] ?? ''), '/');
    if ($base === '') {
        throw new Exception("SMARTAPI_BASE not configured");
    }

    // TOTP (GoogleAuthenticator)
    $totpSecret = $config['SMARTAPI_TOTP_SECRET'] ?? ($config['totp_secret'] ?? '');
    if ($totpSecret === '') {
        throw new Exception("TOTP secret is not configured");
    }
    $ga = new PHPGangsta_GoogleAuthenticator();
    $totp = $ga->getCode($totpSecret);

    // Build request
    $url = $base . '/rest/auth/angelbroking/user/v1/loginByPassword';
    $headers = [
        'X-UserType' => 'USER',
        'X-SourceID' => 'WEB',
        'X-ClientLocalIP' => $config['SMARTAPI_LOCAL_IP'] ?? '127.0.0.1',
        'X-ClientPublicIP' => $config['SMARTAPI_PUBLIC_IP'] ?? '',
        'X-MACAddress' => $config['SMARTAPI_MAC'] ?? '',
        'X-PrivateKey' => $config['SMARTAPI_API_KEY'] ?? ($config['api_key'] ?? '')
    ];

    $loginBody = [
        'clientcode' => $clientcode_input,
        'password' => $pin_input,
        'totp' => (string)$totp
    ];

    list($status, $json, $rawBody) = http_post_json($url, $headers, $loginBody, 25);

    @file_put_contents(sys_get_temp_dir() . '/debug_angel_login.log', date('c')." | HTTP $status | resp: ".substr($rawBody,0,200).PHP_EOL, FILE_APPEND);

    if ($status !== 200 || empty($json) || !($json['status'] ?? false)) {
        $msg = $json['message'] ?? ('HTTP ' . $status);
        send_json(['status'=>'error','message'=>"SmartAPI login failed: {$msg}"], 502);
    }

    $data = $json['data'] ?? null;
    if (!$data || empty($data['jwtToken'])) {
        throw new Exception("SmartAPI did not return jwtToken");
    }

    $session = [
        'jwtToken' => $data['jwtToken'],
        'refreshToken' => $data['refreshToken'] ?? null,
        'feedToken' => $data['feedToken'] ?? null,
        'last_login_client_code' => $clientcode_input,
        'created_at' => time()
    ];

    $sessionFile = $config['SMARTAPI_SESSION_FILE'] ?? ($config['session_file'] ?? __DIR__ . '/../storage/smartapi_session.json');

    // ensure parent dir exists
    $parent = dirname($sessionFile);
    if (!is_dir($parent)) {
        if (!mkdir($parent, 0750, true)) {
            throw new Exception("Cannot create session directory: {$parent}");
        }
    }

    // write atomically
    safe_write_json_file($sessionFile, $session);

    // create manual connect flag
    @file_put_contents(dirname($sessionFile) . '/smartapi_manual_connect.flag', (string)time());

    send_json([
        'status' => 'ok',
        'message' => 'Connected to SmartAPI and session saved.',
        'sessionFile' => $sessionFile,
        'serverTs' => time()
    ], 200);

} catch (Exception $e) {
    @file_put_contents(__DIR__ . '/../storage/logs/angel_connect_error.log', date('c')." | ERROR: ".$e->getMessage().PHP_EOL, FILE_APPEND);
    send_json(['status'=>'error','message' => $e->getMessage()], 500);
}
