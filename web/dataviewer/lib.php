<?php
/* Shared helpers: config, session auth, SigV4 signing for B2's S3 API. PHP 7.3 compatible. */

if (!defined('BAILE_CONFIG')) {
    $cands = array(
        dirname(__DIR__, 4) . '/baile_private/config.php',   // /webspace/baile_private  (preferred, not web-reachable)
        dirname(__DIR__, 3) . '/baile_private/config.php',   // /webspace/httpdocs/baile_private
    );
    $found = $cands[0];
    foreach ($cands as $p) { if (is_file($p)) { $found = $p; break; } }
    define('BAILE_CONFIG', $found);
    define('BAILE_CONFIG_TRIED', implode("\n", $cands));
}

function cfg() {
    static $c = null;
    if ($c === null) {
        if (!is_file(BAILE_CONFIG)) {
            http_response_code(500);
            header('Content-Type: text/plain');
            echo "Viewer not configured: config.php not found. Tried:\n" . BAILE_CONFIG_TRIED;
            exit;
        }
        $c = require BAILE_CONFIG;
    }
    return $c;
}

function start_session() {
    if (session_status() !== PHP_SESSION_ACTIVE) {
        $secure = (!empty($_SERVER['HTTPS']) && $_SERVER['HTTPS'] !== 'off');
        session_set_cookie_params(0, '/', '', $secure, true);
        session_name('bnview');
        session_start();
    }
}

function auth_required() {
    $c = cfg();
    return !empty($c['password_hash']);
}

function is_logged_in() {
    if (!auth_required()) return true;
    start_session();
    return !empty($_SESSION['bn_ok']);
}

function try_login($password) {
    $c = cfg();
    start_session();
    if (password_verify((string)$password, $c['password_hash'])) {
        session_regenerate_id(true);
        $_SESSION['bn_ok'] = 1;
        $_SESSION['csrf'] = bin2hex(random_bytes(16));
        return true;
    }
    usleep(400000);
    return false;
}

function csrf_token() {
    start_session();
    if (empty($_SESSION['csrf'])) $_SESSION['csrf'] = bin2hex(random_bytes(16));
    return $_SESSION['csrf'];
}

/* Bucket registry. config 'buckets' => id => (title, bucket, key_id, app_key, allowed_prefixes, root, figures).
   A config without 'buckets' (single bucket, top-level keys) still works as bucket 'main'. */
function buckets() {
    static $b = null;
    if ($b !== null) return $b;
    $c = cfg();
    $raw = !empty($c['buckets']) ? $c['buckets'] : array('main' => array(
        'title' => $c['bucket'], 'bucket' => $c['bucket'], 'key_id' => $c['key_id'], 'app_key' => $c['app_key'],
        'allowed_prefixes' => $c['allowed_prefixes'], 'root' => $c['allowed_prefixes'][0], 'figures' => true));
    $b = array();
    foreach ($raw as $id => $x) {
        $x += array('title' => $id, 'allowed_prefixes' => array(''), 'figures' => false,
                    'endpoint' => $c['endpoint'], 'region' => $c['region']);
        if (!isset($x['root'])) $x['root'] = $x['allowed_prefixes'][0];
        $b[$id] = $x;
    }
    return $b;
}

function bucket($id = null) {
    $all = buckets();
    if ($id === null || $id === '') { foreach ($all as $x) return $x; }
    return isset($all[$id]) ? $all[$id] : null;
}

function figures_bucket() {
    foreach (buckets() as $x) if (!empty($x['figures'])) return $x;
    return null;
}

function key_allowed($key, $bk = null) {
    $c = $bk ? $bk : bucket();
    if (strpos($key, '..') !== false || strpos($key, "\0") !== false) return false;
    foreach ($c['allowed_prefixes'] as $p) {
        if (strpos($key, $p) === 0) return true;
    }
    return false;
}

function rfc3986($s) {
    return str_replace('%7E', '~', rawurlencode($s));
}

function enc_path($key) {
    $parts = explode('/', $key);
    $out = array();
    foreach ($parts as $p) $out[] = rfc3986($p);
    return implode('/', $out);
}

/* Build a presigned GET URL (query-string SigV4, UNSIGNED-PAYLOAD). $key '' = bucket. */
function s3_presign($key, $params = array(), $expires = 900, $bk = null) {
    $c = $bk ? $bk : bucket();
    $amzDate = gmdate('Ymd\THis\Z');
    $date = substr($amzDate, 0, 8);
    $scope = $date . '/' . $c['region'] . '/s3/aws4_request';
    $q = $params;
    $q['X-Amz-Algorithm'] = 'AWS4-HMAC-SHA256';
    $q['X-Amz-Credential'] = $c['key_id'] . '/' . $scope;
    $q['X-Amz-Date'] = $amzDate;
    $q['X-Amz-Expires'] = (string)$expires;
    $q['X-Amz-SignedHeaders'] = 'host';
    ksort($q, SORT_STRING);
    $pairs = array();
    foreach ($q as $k => $v) $pairs[] = rfc3986($k) . '=' . rfc3986((string)$v);
    $qs = implode('&', $pairs);
    $path = '/' . rfc3986($c['bucket']) . ($key !== '' ? '/' . enc_path($key) : '');
    $canonical = "GET\n" . $path . "\n" . $qs . "\nhost:" . $c['endpoint'] . "\n\nhost\nUNSIGNED-PAYLOAD";
    $sts = "AWS4-HMAC-SHA256\n" . $amzDate . "\n" . $scope . "\n" . hash('sha256', $canonical);
    $k = hash_hmac('sha256', $date, 'AWS4' . $c['app_key'], true);
    $k = hash_hmac('sha256', $c['region'], $k, true);
    $k = hash_hmac('sha256', 's3', $k, true);
    $k = hash_hmac('sha256', 'aws4_request', $k, true);
    $sig = hash_hmac('sha256', $sts, $k);
    return 'https://' . $c['endpoint'] . $path . '?' . $qs . '&X-Amz-Signature=' . $sig;
}

/* Server-side GET; returns array(status, body). */
function http_get($url, $maxBytes = 8388608) {
    $ch = curl_init($url);
    $buf = '';
    curl_setopt_array($ch, array(
        CURLOPT_RETURNTRANSFER => false,
        CURLOPT_FOLLOWLOCATION => false,
        CURLOPT_CONNECTTIMEOUT => 10,
        CURLOPT_TIMEOUT => 60,
        CURLOPT_WRITEFUNCTION => function ($ch, $data) use (&$buf, $maxBytes) {
            $buf .= $data;
            return (strlen($buf) > $maxBytes) ? 0 : strlen($data);
        },
    ));
    curl_exec($ch);
    $status = (int)curl_getinfo($ch, CURLINFO_HTTP_CODE);
    curl_close($ch);
    return array($status, $buf);
}

function json_out($data, $status = 200) {
    http_response_code($status);
    header('Content-Type: application/json; charset=utf-8');
    header('Cache-Control: no-store');
    header('X-Content-Type-Options: nosniff');
    echo json_encode($data, JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE);
    exit;
}
