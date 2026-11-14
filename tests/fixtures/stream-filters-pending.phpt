--TEST--
Pending quoted-printable CR waits for the following LF chunk
--FILE--
<?php
function run_filter($name,$chunks,$options) {
    $stream=fopen('php://temp','w+b');
    $filter=stream_filter_append($stream,'convert.'.$name,STREAM_FILTER_WRITE,$options);
    if($filter===false){throw new Exception('synthetic filter creation failed');}
    foreach($chunks as $chunk) { if(fwrite($stream,$chunk)!==strlen($chunk)){throw new Exception('synthetic short write');} }
    if(!stream_filter_remove($filter)){throw new Exception('synthetic filter close failed');}
    rewind($stream);$result=stream_get_contents($stream);fclose($stream);return $result;
}
echo bin2hex(run_filter('quoted-printable-decode',array("A=\r","\nB"),null)),"\n";
--EXPECT--
4142
