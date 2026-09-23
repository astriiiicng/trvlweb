<?php

use Illuminate\Foundation\Application;
use Illuminate\Http\Request;

define('LARAVEL_START', microtime(true));

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

// Create SQLite database file if it doesn't exist
if (!file_exists($tmpStorage . '/database.sqlite')) {
    @touch($tmpStorage . '/database.sqlite');
}

require __DIR__ . '/../vendor/autoload.php';

/** @var Application $app */
$app = require_once __DIR__ . '/../bootstrap/app.php';

$app->useStoragePath($tmpStorage);

$app->handleRequest(Request::capture());
