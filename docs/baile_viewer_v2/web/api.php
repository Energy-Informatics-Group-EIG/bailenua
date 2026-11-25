<?php
/*
 * Baile Nua viewer API (AJAX). PHP 7.3+.
 *
 *   GET  api.php?a=index                      figures index (tabs -> figures)
 *   GET  api.php?a=figure&id=e_annual[&year=2025]
 *   GET  api.php?a=list&prefix=v1/2025/
 *   GET  api.php?a=presign&key=v1/2025/observable/D19_part000.parquet
 *   GET  api.php?a=text&key=v1/2025/_segment/DONE.json
 *   POST api.php?a=login     password=...
 *   POST api.php?a=logout
 *
 * The B2 key never leaves the server; the browser only receives short-lived
 * presigned URLs for files under the allowed prefixes.
 */
require __DIR__ . '/lib.php';

$a = isset($_GET['a']) ? $_GET['a'] : '';

if ($a === 'login' && $_SERVER['REQUEST_METHOD'] === 'POST') {
    $ok = try_login(isset($_POST['password']) ? $_POST['password'] : '');
    json_out(array('ok' => $ok), $ok ? 200 : 401);
}
if ($a === 'logout' && $_SERVER['REQUEST_METHOD'] === 'POST') {
    start_session();
    $_SESSION = array();
    session_destroy();
    json_out(array('ok' => true));
}
if (!is_logged_in()) {
    json_out(array('error' => 'login required'), 401);
}

$c = cfg();

function cached_object($key) {
    $c = cfg();
    // Optional: figures copied to the web server instead of read from B2.
    if (!empty($c['local_figures_dir']) && strpos($key, $c['figures_prefix']) === 0) {
        $f = rtrim($c['local_figures_dir'], '/') . '/' . basename($key);
        return is_file($f) ? file_get_contents($f) : null;
    }
    $dir = $c['cache_dir'];
    if (!is_dir($dir)) @mkdir($dir, 0700, true);
    $file = $dir . '/' . sha1($key) . '.json';
    if (is_file($file) && (time() - filemtime($file)) < $c['cache_ttl_s']) {
        return file_get_contents($file);
    }
    list($status, $body) = http_get(s3_presign($key));
    if ($status !== 200) return null;
    @file_put_contents($file, $body, LOCK_EX);
    return $body;
}

switch ($a) {

case 'index':
    $body = cached_object($c['figures_prefix'] . 'index.json');
    if ($body === null) json_out(array('error' => 'figures index not found; run figures_build.py and upload v1/figures/'), 404);
    header('Content-Type: application/json; charset=utf-8');
    header('Cache-Control: private, max-age=300');
    echo $body;
    exit;

case 'figure':
    $id = isset($_GET['id']) ? $_GET['id'] : '';
    $year = isset($_GET['year']) ? $_GET['year'] : '';
    if (!preg_match('/^[a-z0-9_]{1,64}$/', $id) || ($year !== '' && !preg_match('/^\d{4}$/', $year))) {
        json_out(array('error' => 'bad figure id'), 400);
    }
    $name = $year !== '' ? $id . '@' . $year : $id;
    $body = cached_object($c['figures_prefix'] . $name . '.json');
    if ($body === null) json_out(array('error' => 'figure not found: ' . $name), 404);
    header('Content-Type: application/json; charset=utf-8');
    header('Cache-Control: private, max-age=3600');
    echo $body;
    exit;

case 'list':
    $prefix = isset($_GET['prefix']) ? $_GET['prefix'] : 'v1/';
    if ($prefix === '' || !key_allowed($prefix)) json_out(array('error' => 'prefix not allowed'), 403);
    $params = array('list-type' => '2', 'prefix' => $prefix, 'delimiter' => '/', 'max-keys' => '1000');
    if (!empty($_GET['token'])) $params['continuation-token'] = $_GET['token'];
    list($status, $body) = http_get(s3_presign('', $params));
    if ($status !== 200) json_out(array('error' => 'list failed', 'status' => $status), 502);
    $x = @simplexml_load_string($body);
    if ($x === false) json_out(array('error' => 'bad list response'), 502);
    $dirs = array(); $files = array();
    foreach ($x->CommonPrefixes as $cp) $dirs[] = (string)$cp->Prefix;
    foreach ($x->Contents as $o) {
        $k = (string)$o->Key;
        if ($k === $prefix) continue;
        $files[] = array('key' => $k, 'size' => (int)$o->Size, 'modified' => (string)$o->LastModified);
    }
    json_out(array('prefix' => $prefix, 'dirs' => $dirs, 'files' => $files,
        'next' => ((string)$x->IsTruncated === 'true') ? (string)$x->NextContinuationToken : null));

case 'presign':
    $key = isset($_GET['key']) ? $_GET['key'] : '';
    if ($key === '' || !key_allowed($key)) json_out(array('error' => 'key not allowed'), 403);
    json_out(array('url' => s3_presign($key, array(), 900), 'expires_s' => 900));

case 'text':
    $key = isset($_GET['key']) ? $_GET['key'] : '';
    if ($key === '' || !key_allowed($key) || !preg_match('/\.(json|md|txt|log|csv)$/i', $key)) {
        json_out(array('error' => 'key not allowed'), 403);
    }
    list($status, $body) = http_get(s3_presign($key), 2 * 1024 * 1024);
    if ($status !== 200 && $status !== 0) json_out(array('error' => 'read failed', 'status' => $status), 502);
    header('Content-Type: text/plain; charset=utf-8');
    header('X-Content-Type-Options: nosniff');
    echo $body;
    exit;

default:
    json_out(array('error' => 'unknown action'), 400);
}
