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
@mkdir('/tmp/bootstrap/cache', 0777, true);
if (!file_exists('/tmp/bootstrap/cache/packages.php') && file_exists(__DIR__ . '/../bootstrap/cache/packages.php')) {
    @copy(__DIR__ . '/../bootstrap/cache/packages.php', '/tmp/bootstrap/cache/packages.php');
}
if (!file_exists('/tmp/bootstrap/cache/services.php') && file_exists(__DIR__ . '/../bootstrap/cache/services.php')) {
    @copy(__DIR__ . '/../bootstrap/cache/services.php', '/tmp/bootstrap/cache/services.php');
}

// Normalize script name so Laravel routes starting with /api/ aren't stripped by Symfony's baseUrl resolver
$_SERVER['SCRIPT_NAME'] = '/index.php';
$_SERVER['PHP_SELF'] = '/index.php';

// Create SQLite database file
$isNewDb = false;
if (!file_exists($tmpStorage . '/database.sqlite') || filesize($tmpStorage . '/database.sqlite') === 0) {
    @touch($tmpStorage . '/database.sqlite');
    $isNewDb = true;
}

try {
    define('LARAVEL_START', microtime(true));

    require __DIR__ . '/../vendor/autoload.php';

    /** @var \Illuminate\Foundation\Application $app */
    $app = require_once __DIR__ . '/../bootstrap/app.php';

    $app->useStoragePath($tmpStorage);

    if ($isNewDb) {
        try {
            \Illuminate\Support\Facades\Artisan::call('migrate', ['--force' => true]);
        } catch (\Throwable $mErr) {
            error_log('Migration failed: ' . $mErr->getMessage());
        }
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
