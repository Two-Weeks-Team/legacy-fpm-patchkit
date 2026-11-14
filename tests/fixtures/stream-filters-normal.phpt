--TEST--
Synthetic stream filter normal contracts
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
echo 'base64-plain=',bin2hex(run_filter('base64-encode',array('A','B','C','D'),null)),"\n";
echo 'base64-decode=',bin2hex(run_filter('base64-decode',array('QU','JD','RA=='),null)),"\n";
echo 'base64-wrap=',bin2hex(run_filter('base64-encode',array('AAA','AAA'),array('line-length'=>4,'line-break-chars'=>"\n"))),"\n";
echo 'qp-binary=',bin2hex(run_filter('quoted-printable-encode',array("A=B\0"),array('binary'=>true))),"\n";
echo 'qp-decode=',bin2hex(run_filter('quoted-printable-decode',array('A=3','DB=0','0'),null)),"\n";
echo 'qp-custom=',bin2hex(run_filter('quoted-printable-decode',array('A=3DB',"=\r\n",'C'),array('line-break-chars'=>"\r\n"))),"\n";
echo 'qp-force-first=',bin2hex(run_filter('quoted-printable-encode',array('ABC'),array('line-length'=>8,'binary'=>true,'force-encode-first'=>true))),"\n";
echo 'short-line=',bin2hex(run_filter('base64-encode',array('AAAAAA'),array('line-length'=>3,'line-break-chars'=>'X'))),"\n";
echo "COMPLETE=yes\n";
--EXPECT--
base64-plain=51554a4452413d3d
base64-decode=41424344
base64-wrap=515546420a51554642
qp-binary=413d3344423d3030
qp-decode=413d4200
qp-custom=413d4243
qp-force-first=3d34314243
short-line=5155464251554642
COMPLETE=yes
