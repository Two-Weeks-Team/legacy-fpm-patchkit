--TEST--
Benign legacy worker-log byte producer contract (CLI only, not the FPM sink)
--FILE--
<?php
$payload = "Pre\0SecretTail\nNEXT\nliteral\\x00\n%s %n %%\n";
$stream = fopen('php://temp', 'w+b');
$written = fwrite($stream, $payload);
rewind($stream);
$actual = stream_get_contents($stream);
fclose($stream);
echo $written, "\n", bin2hex($actual), "\n";
?>
--EXPECT--
41
507265005365637265745461696c0a4e4558540a6c69746572616c5c7830300a257320256e2025250a
