--TEST--
Multipart body-parts default is the derived-limit sentinel
--FILE--
<?php
var_dump(ini_get('max_multipart_body_parts'));
?>
--EXPECT--
string(2) "-1"
