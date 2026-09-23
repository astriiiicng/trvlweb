<?php

// Enable error display for debugging
error_reporting(E_ALL);
ini_set('display_errors', '1');

// Create writable directories in /tmp (Vercel filesystem is read-only)
$tmpStorage = '/tmp/storage';

foreach ([
    '/framework/views',
    '/framework/cache/data',
    '/framework/sessions',
    '/logs'
] as $dir) {
    @mkdir($tmpStorage . $dir, 0777, true);
}

// APP_PACKAGES_CACHE and APP_SERVICES_CACHE (set in vercel.json) point here
// so the directory must exist before Laravel tries to write cache files
@mkdir('/tmp/bootstrap/cache', 0777, true);

// Create SQLite database file
if (!file_exists($tmpStorage . '/database.sqlite')) {
    @touch($tmpStorage . '/database.sqlite');
}

try {
    define('LARAVEL_START', microtime(true));

    require __DIR__ . '/../vendor/autoload.php';

    /** @var \Illuminate\Foundation\Application $app */
    $app = require_once __DIR__ . '/../bootstrap/app.php';

    $app->useStoragePath($tmpStorage);

    if (isset($_SERVER['HTTP_X_FORWARDED_PROTO']) && $_SERVER['HTTP_X_FORWARDED_PROTO'] === 'https') {
        $_SERVER['HTTPS'] = 'on';
    }

    $app->handleRequest(\Illuminate\Http\Request::capture());

} catch (\Throwable $e) {
    http_response_code(500);
    header('Content-Type: text/plain; charset=utf-8');
    echo "=== LARAVEL BOOT ERROR ===\n\n";
    echo "Message: " . $e->getMessage() . "\n";
    echo "File: " . $e->getFile() . "\n";
    echo "Line: " . $e->getLine() . "\n\n";
    echo "=== STACK TRACE ===\n";
    echo $e->getTraceAsString();
}
