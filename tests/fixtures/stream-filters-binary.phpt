--TEST--
Synthetic stream filter binary contracts
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
echo 'base64-nul=',bin2hex(run_filter('base64-encode',array('AAAAAA'),array('line-length'=>4,'line-break-chars'=>"\0X"))),"\n";
echo 'qp-encode-nul=',bin2hex(run_filter('quoted-printable-encode',array('AAAAAA'),array('line-length'=>4,'binary'=>true,'line-break-chars'=>"\0X"))),"\n";
echo 'qp-decode-nul=',bin2hex(run_filter('quoted-printable-decode',array("=\0XAB"),array('line-break-chars'=>"\0X"))),"\n";
echo 'base64-middle-nul=',bin2hex(run_filter('base64-encode',array('AAAAAA'),array('line-length'=>4,'line-break-chars'=>"\r\0\n"))),"\n";
echo 'qp-decode-middle-nul=',bin2hex(run_filter('quoted-printable-decode',array("=X\0YAB"),array('line-break-chars'=>"X\0Y"))),"\n";
echo 'custom-eof=',bin2hex(run_filter('quoted-printable-decode',array("=\r\n"),array('line-break-chars'=>"\r\n"))),"\n";
echo 'auto-cr-eof=',bin2hex(run_filter('quoted-printable-decode',array("A=\r"),null)),"\n";
echo 'base64-empty-option=',bin2hex(run_filter('base64-encode',array('AAAAAA'),array('line-length'=>4,'line-break-chars'=>''))),"\n";
echo 'qp-empty-option=',bin2hex(run_filter('quoted-printable-encode',array('AAAAAA'),array('line-length'=>4,'binary'=>true,'line-break-chars'=>''))),"\n";
echo "COMPLETE=yes\n";
--EXPECT--
base64-nul=51554642005851554642
qp-encode-nul=4141413d0058414141
qp-decode-nul=4142
base64-middle-nul=515546420d000a51554642
qp-decode-middle-nul=4142
custom-eof=
auto-cr-eof=41
base64-empty-option=5155464251554642
qp-empty-option=4141413d414141
COMPLETE=yes
