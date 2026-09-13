<?php
declare(strict_types=1);
function e(?string $v): string { return htmlspecialchars($v??'',ENT_QUOTES|ENT_SUBSTITUTE,'UTF-8'); }
function csrf_token(): string { if(empty($_SESSION['csrf'])) $_SESSION['csrf']=bin2hex(random_bytes(32)); return $_SESSION['csrf']; }
function verify_csrf(?string $t): void { if(!$t || !hash_equals($_SESSION['csrf']??'',$t)){http_response_code(419);exit('Sicherheitsprüfung fehlgeschlagen. Bitte Seite neu laden.');}}
function random_token(int $bytes=32): string { return bin2hex(random_bytes($bytes)); }
function token_hash(string $token): string { return hash('sha256',$token); }
function client_ip(): string { return substr($_SERVER['REMOTE_ADDR']??'unknown',0,64); }
function json_input(): array { $raw=file_get_contents('php://input')?:''; if($raw==='') return []; $d=json_decode($raw,true); return is_array($d)?$d:[]; }
function json_response(array $p,int $s=200): never { http_response_code($s);header('Content-Type: application/json; charset=utf-8');header('Cache-Control: no-store');echo json_encode($p,JSON_UNESCAPED_UNICODE|JSON_UNESCAPED_SLASHES);exit; }
function normalize_email(string $e): string { return mb_strtolower(trim($e)); }
function valid_username(string $u): bool { return (bool)preg_match('/^[A-Za-z0-9._-]{3,32}$/',$u); }
function enforce_login_rate_limit(string $identity): void {
    global $config; $window=max(1,(int)($config['security']['login_window_minutes']??15)); $max=max(3,(int)($config['security']['login_max_attempts']??8));
    $q=db()->prepare("SELECT COUNT(*) FROM login_attempts WHERE success=0 AND attempted_at >= (NOW() - INTERVAL {$window} MINUTE) AND (identity=? OR ip_address=?)");
    $q->execute([$identity,client_ip()]);
    if((int)$q->fetchColumn()>=$max) json_response(['ok'=>false,'error'=>'rate_limited','message'=>'Zu viele fehlgeschlagene Anmeldeversuche. Bitte später erneut versuchen.'],429);
}
function record_login_attempt(string $identity,bool $success): void { $q=db()->prepare('INSERT INTO login_attempts(identity,ip_address,success,attempted_at) VALUES(?,?,?,NOW())');$q->execute([$identity,client_ip(),$success?1:0]); }
