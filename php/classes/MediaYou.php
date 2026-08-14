<?php
/**
 * MediaYou compatibility helpers for Magic Systech based radios.
 */
defined('HAMARadio') or die('Invalid Endpoint');

class MediaYou {

	public const SERIAL_PREG = '/^[0-9A-F]{12}$/';

	/**
	 * Parse CONF_MEDIAYOU_DEVICES (SERIAL=PROFILE_ID,...).
	 */
	public static function parseDeviceMap(string $config) : array {
		$devices = array();

		foreach(explode(',', $config) as $mapping){
			$parts = array_map('trim', explode('=', $mapping, 2));
			if(count($parts) !== 2){
				continue;
			}

			$serial = self::normalizeSerial($parts[0]);
			$profile = filter_var($parts[1], FILTER_VALIDATE_INT, array(
				'options' => array('min_range' => 1, 'max_range' => 9999)
			));
			if(!is_null($serial) && $profile !== false){
				$devices[$serial] = $profile;
			}
		}

		return $devices;
	}

	public static function normalizeSerial(mixed $serial) : ?string {
		if(!is_string($serial)){
			return null;
		}

		$serial = strtoupper(str_replace(array(':', '-'), '', trim($serial)));
		return preg_match(self::SERIAL_PREG, $serial) === 1 ? $serial : null;
	}

	public static function profileForSerial(string $serial, array $devices) : ?int {
		return isset($devices[$serial]) ? intval($devices[$serial]) : null;
	}

	/**
	 * Build the compact record stream consumed by GetMyMediaU_sn4 clients.
	 */
	public static function favorites(array $stations, string $baseUrl, string $serial) : string {
		$baseUrl = rtrim($baseUrl, '/') . '/';
		$out = 'T,O,0,*{*{Favorites}*}*,<br>';
		$count = 0;

		foreach($stations as $index => $station){
			if(
				!is_array($station) ||
				!isset($station['name'], $station['url']) ||
				!in_array($station['category'] ?? '', array('Favorites', 'Favoriten'), true)
			){
				continue;
			}

			$id = intval($index) + 1000;
			$url = $baseUrl . 'mediayou.php?' . http_build_query(array(
				'action' => 'play',
				'id' => $id,
				'serial' => $serial
			));
			$out .= 'S,O,0,*{*{' . self::cleanLabel(strval($station['name'])) . '}*}*,' . $url . '<br>';
			$count++;
		}

		return $count === 0 ? '!{!{NONE}!}!' : $out;
	}

	public static function asx(string $title, string $url) : string {
		$title = htmlspecialchars($title, ENT_QUOTES | ENT_XML1, 'UTF-8');
		$url = htmlspecialchars($url, ENT_QUOTES | ENT_XML1, 'UTF-8');
		return '<ASX version="3.0"><TITLE>' . $title . '</TITLE><Entry><ref href="' . $url . '"/></Entry></ASX>';
	}

	private static function cleanLabel(string $label) : string {
		$label = str_replace(array('*{*{', '}*}*', '<br>', ',', "\0"), ' ', $label);
		$label = preg_replace('/[\x00-\x1F\x7F]+/', ' ', $label);
		$label = preg_replace('/\s+/', ' ', trim($label));
		return substr($label, 0, 98);
	}
}
?>
