<?php
declare(strict_types=1);
$configFile = __DIR__ . '/../config/local.php';
if (!is_file($configFile)) {
    $requested = $_SERVER['REQUEST_URI'] ?? '';
    if (!str_contains($requested, '/install/')) {
        header('Location: install/');
        exit;
    }
    return;
}
$config = require $configFile;
date_default_timezone_set($config['app']['timezone'] ?? 'Europe/Berlin');
$secure = (!empty($_SERVER['HTTPS']) && $_SERVER['HTTPS'] !== 'off');
session_name($config['app']['session_name'] ?? 'justincard_session');
session_set_cookie_params(['lifetime'=>0,'path'=>'/','secure'=>$secure,'httponly'=>true,'samesite'=>'Lax']);
if (session_status() !== PHP_SESSION_ACTIVE) session_start();
require_once __DIR__ . '/db.php';
require_once __DIR__ . '/security.php';
require_once __DIR__ . '/auth.php';
