--TEST--
Multipart body-parts setting is registered and cannot be raised by user code
--INI--
max_multipart_body_parts=3
--FILE--
<?php
var_dump(ini_get('max_multipart_body_parts'));
var_dump(ini_set('max_multipart_body_parts','4'));
var_dump(ini_get('max_multipart_body_parts'));
?>
--EXPECT--
string(1) "3"
bool(false)
string(1) "3"
