<?php
/**
 * Compatibility endpoint for MediaYou/Magic Systech radios.
 */
define('HAMARadio', 'Radio');
error_reporting(!empty($_ENV['DEV']) && $_ENV['DEV'] == 'dev' ? E_ALL : 0);

require_once(__DIR__ . '/classes/autoload.php');

function mediaYouSend(string $body, string $contentType = 'text/plain; charset=utf-8', int $status = 200) : never {
	http_response_code($status);
	header('Content-Type: ' . $contentType);
	header('Cache-Control: no-store, no-cache, must-revalidate');
	header('Content-Length: ' . strlen($body));
	die($body);
}

function mediaYouStation(Data $data, mixed $id) : array {
	if(!is_string($id) || preg_match('/^[0-9]{4}$/', $id) !== 1){
		mediaYouSend('Invalid station ID', 'text/plain; charset=utf-8', 400);
	}

	$station = $data->getById(intval($id));
	if(empty($station) || empty($station['name']) || empty($station['url'])){
		mediaYouSend('Unknown station', 'text/plain; charset=utf-8', 404);
	}
	return $station;
}

function mediaYouProxy(array $station) : never {
	$url = Helper::getFinalUrl(strval($station['url']));
	$parts = parse_url($url);
	$host = isset($parts['host']) ? strval($parts['host']) : '';
	$ip = $host !== '' ? gethostbyname($host) : '';

	if(
		!isset($parts['scheme']) ||
		!in_array($parts['scheme'], array('http', 'https'), true) ||
		$host === '' ||
		filter_var($ip, FILTER_VALIDATE_IP, FILTER_FLAG_NO_PRIV_RANGE | FILTER_FLAG_NO_RES_RANGE) === false
	){
		mediaYouSend('Invalid stream URL', 'text/plain; charset=utf-8', 502);
	}

	$authority = $ip . (isset($parts['port']) ? ':' . intval($parts['port']) : '');
	$path = $parts['path'] ?? '/';
	$query = isset($parts['query']) ? '?' . $parts['query'] : '';
	$resolvedUrl = $parts['scheme'] . '://' . $authority . $path . $query;
	$proxy = !empty($station['nometa']) ? '/proxy-nometa/' : '/proxy/';

	header('X-Accel-Redirect: ' . $proxy . $host . '/?' . $resolvedUrl);
	die();
}

$serial = MediaYou::normalizeSerial($_GET['SER2'] ?? $_GET['serial'] ?? null);
$devices = MediaYou::parseDeviceMap(Config::MEDIAYOU_DEVICES);
$profile = is_null($serial) ? null : MediaYou::profileForSerial($serial, $devices);
$action = isset($_GET['action']) && is_string($_GET['action']) ? $_GET['action'] : '';

if(is_null($serial)){
	mediaYouSend('!{!{FAIL}!}!', 'text/html; charset=utf-8', 400);
}
if(is_null($profile)){
	mediaYouSend('!{!{NONE}!}!', 'text/html; charset=utf-8');
}

Config::checkAccess($serial);
$data = new Data($profile, true);

if($action === 'favorites'){
	mediaYouSend(MediaYou::favorites($data->getRadioList(), Config::RADIO_DOMAIN, $serial), 'text/html; charset=utf-8');
}

$station = mediaYouStation($data, $_GET['id'] ?? null);

if($action === 'play'){
	$url = strval($station['url']);
	if(!empty($station['proxy'])){
		$url = rtrim(Config::RADIO_DOMAIN, '/') . '/mediayou.php?' . http_build_query(array(
			'action' => 'stream',
			'id' => $_GET['id'],
			'serial' => $serial
		));
	}
	mediaYouSend(MediaYou::asx(strval($station['name']), $url), 'video/x-ms-asf');
}
if($action === 'stream' && !empty($station['proxy'])){
	mediaYouProxy($station);
}

mediaYouSend('Invalid action', 'text/plain; charset=utf-8', 400);
?>
