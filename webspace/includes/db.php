<?php
declare(strict_types=1);
function db(): PDO {
    static $pdo = null; global $config;
    if ($pdo instanceof PDO) return $pdo;
    $d=$config['db'];
    $dsn=sprintf('mysql:host=%s;port=%d;dbname=%s;charset=%s',$d['host'],(int)($d['port']??3306),$d['name'],$d['charset']??'utf8mb4');
    $pdo=new PDO($dsn,$d['user'],$d['password'],[
        PDO::ATTR_ERRMODE=>PDO::ERRMODE_EXCEPTION,
        PDO::ATTR_DEFAULT_FETCH_MODE=>PDO::FETCH_ASSOC,
        PDO::ATTR_EMULATE_PREPARES=>false,
    ]);
    return $pdo;
}
