<?php
// Exercise Router pagination with a played episode and a feed larger than the
// radio response limit, without network requests or production history.
define('HAMARadio', 'Radio');
enum ClientType { case RadioJSON; }
enum OutputPlayStatus { case Info; }
class Config { const RADIO_DOMAIN = 'http://radio.test/'; }
class Id {
    function getId() { return 2; }
    function getMac() { return 'test'; }
}
class Data {
    function __construct($id) {}
    function getTypes() { return [3 => 'Podcast']; }
    function getById($id) { return ['category' => '']; }
    function getPodcastURL($id, $eid, $mac, $sloppy) { return 'http://audio.test/' . $eid; }
}
class UnRead {
    function __construct($id) {}
    function searchItem($id) {}
    function knownItemMark($id, $url) { return $url === '1' ? '' : '*'; }
}
class RadioBrowser { function __construct($id) {} }
class PodcastLoader {
    static function getPodcastDataById($id, $data) {
        $episodes = [];
        for($i = 1; $i <= 405; $i++) {
            $episodes[$i] = ['title' => 'Episode ' . $i, 'url' => (string)$i, 'desc' => ''];
        }
        return ['title' => 'Test', 'logo' => '', 'episodes' => $episodes];
    }
}
class Output {}
class OutputJSON extends Output {
    static $latest;
    public $episodes = [], $next = '', $previous = '';
    function __construct() { self::$latest = $this; }
    function prevUrl($url) { $this->previous = $url; }
    function currentUrl($url, $title) {}
    function addDir($title, $url, $last) { $this->next = $url; }
    function addEpisode($id, $eid, $show, $title, $url, $desc, $logo, $top, $status) {
        if($top) { throw new Exception('Playback must not change episode ordering'); }
        $this->episodes[] = [$eid, $title];
    }
}
require __DIR__ . '/../php/classes/Router.php';
$seen = [];
for($page = 0; $page < 5; $page++) {
    $_GET = ['tid' => 3, 'id' => '3000', 'page' => (string)$page];
    $router = new Router(new Id(), ClientType::RadioJSON);
    $router->handleGet('/list');
    $out = OutputJSON::$latest;
    if(count($out->episodes) > 100) { throw new Exception('Page exceeds limit'); }
    if(($page < 4) !== ($out->next !== '')) { throw new Exception('Invalid next page'); }
    if($page > 0 && !str_ends_with($out->previous, 'page=' . ($page - 1))) {
        throw new Exception('Invalid previous page');
    }
    $seen = array_merge($seen, array_column($out->episodes, 0));
    if($page === 0 && $out->episodes[0] !== [1, 'Episode 1']) {
        throw new Exception('Played episode missing or reordered');
    }
}
if($seen !== range(1, 405)) { throw new Exception('Episodes missing or duplicated across pages'); }
echo "Podcast listing tests passed\n";
