<?php
declare(strict_types=1);require __DIR__.'/_init.php';try{db()->query('SELECT 1');json_response(['ok'=>true,'service'=>'Just InCard API','database'=>'online','time'=>gmdate(DATE_ATOM)]);}catch(Throwable $e){json_response(['ok'=>false,'service'=>'Just InCard API','database'=>'offline'],503);}
