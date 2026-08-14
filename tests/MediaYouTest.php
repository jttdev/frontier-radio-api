<?php
define('HAMARadio', 'Radio');
require_once(__DIR__ . '/../php/classes/MediaYou.php');

function assertSameValue(mixed $expected, mixed $actual, string $message) : void {
	if($expected !== $actual){
		fwrite(STDERR, $message . "\nExpected: " . var_export($expected, true) . "\nActual: " . var_export($actual, true) . "\n");
		exit(1);
	}
}

$devices = MediaYou::parseDeviceMap('ACA2132A1A7A=2, 00:22:61:41:ED:60=3,invalid=4,bad=0');
assertSameValue(array('ACA2132A1A7A' => 2, '00226141ED60' => 3), $devices, 'Device map parsing failed');
assertSameValue('ACA2132A1A7A', MediaYou::normalizeSerial('ac:a2:13:2a:1a:7a'), 'Serial normalization failed');
assertSameValue(null, MediaYou::normalizeSerial('not-a-mac'), 'Invalid serial accepted');

$stations = array(
	array('name' => 'Jazz, Soul', 'url' => 'http://example.test/jazz', 'category' => 'Favorites'),
	array('name' => 'Ignored', 'url' => 'http://example.test/ignored', 'category' => 'Other'),
	array('name' => 'Pop', 'url' => 'http://example.test/pop', 'category' => 'Favoriten')
);
$favorites = MediaYou::favorites($stations, 'http://10.3.0.12/', 'ACA2132A1A7A');
$expected = 'T,O,0,*{*{Favorites}*}*,<br>'
	. 'S,O,0,*{*{Jazz Soul}*}*,http://10.3.0.12/mediayou.php?action=play&id=1000&serial=ACA2132A1A7A<br>'
	. 'S,O,0,*{*{Pop}*}*,http://10.3.0.12/mediayou.php?action=play&id=1002&serial=ACA2132A1A7A<br>';
assertSameValue($expected, $favorites, 'Favorites response generation failed');
assertSameValue('!{!{NONE}!}!', MediaYou::favorites(array(), 'http://10.3.0.12', 'ACA2132A1A7A'), 'Empty response generation failed');
assertSameValue(
	'<ASX version="3.0"><TITLE>A &amp; B</TITLE><Entry><ref href="http://example.test/?a=1&amp;b=2"/></Entry></ASX>',
	MediaYou::asx('A & B', 'http://example.test/?a=1&b=2'),
	'ASX escaping failed'
);

echo "MediaYou tests passed\n";
?>
