<?php
declare(strict_types=1);
return [
    'app' => [
        'name' => 'Just InCard',
        'base_url' => 'https://example.de',
        'session_name' => 'justincard_session',
        'timezone' => 'Europe/Berlin',
    ],
    'db' => [
        'host' => 'db000000.hosting-data.io',
        'port' => 3306,
        'name' => 'dbs000000',
        'user' => 'dbo000000',
        'password' => 'CHANGE_ME',
        'charset' => 'utf8mb4',
    ],
    'security' => [
        'token_ttl_days' => 90,
        'login_window_minutes' => 15,
        'login_max_attempts' => 8,
    ],
];
