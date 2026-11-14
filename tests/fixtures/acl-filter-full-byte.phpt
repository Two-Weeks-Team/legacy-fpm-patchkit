--TEST--
GHSA-ch8v-r6jh-4vvr: full byte range and ordinary FILTER_SANITIZE_ENCODED behavior
--SKIPIF--
<?php if (!extension_loaded('filter')) die('skip filter extension required'); ?>
--FILE--
<?php
// Exercise the full byte domain and preserve ordinary filter behavior.
// The original can pass by chance; this fixture alone is never a RED proof.
$failures = 0;
$safe = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-._';
for ($i = 0; $i < 256; $i++) {
    $input = chr($i);
    $expected = strpos($safe, $input) !== false ? $input : sprintf('%%%02X', $i);
    $actual = filter_var($input, FILTER_SANITIZE_ENCODED);
    if ($actual !== $expected) {
        echo 'byte ', $i, ' expected=', bin2hex($expected), ' actual=', bin2hex($actual), "\n";
        $failures++;
    }
}
$cases = array(
    array('', 0, ''),
    array($safe, 0, $safe),
    array('https://example.test/a b?q=1&x=~', 0, 'https%3A%2F%2Fexample.test%2Fa%20b%3Fq%3D1%26x%3D%7E'),
    array("A\x00\x1f\x7f\x80\xfe\xffZ", 0, 'A%00%1F%7F%80%FE%FFZ'),
    array("A\x00\x1f \xffZ", FILTER_FLAG_STRIP_LOW, 'A%20%FFZ'),
    array("A\x1f\x7f\x80\xffZ", FILTER_FLAG_STRIP_HIGH, 'A%1FZ'),
    array('A`B~', FILTER_FLAG_STRIP_BACKTICK, 'AB%7E'),
    array("\x00A` \xffZ", FILTER_FLAG_STRIP_LOW | FILTER_FLAG_STRIP_HIGH | FILTER_FLAG_STRIP_BACKTICK, 'A%20Z'),
    array("A\x00\x1fZ", FILTER_FLAG_ENCODE_LOW, 'A%00%1FZ'),
    array("A\x7f\x80\xffZ", FILTER_FLAG_ENCODE_HIGH, 'A%7F%80%FFZ'),
    array('A&B', FILTER_FLAG_ENCODE_AMP, 'A%26B'),
    array("A\x00&\xffZ", FILTER_FLAG_ENCODE_LOW | FILTER_FLAG_ENCODE_HIGH | FILTER_FLAG_ENCODE_AMP, 'A%00%26%FFZ'),
    array(str_repeat('A z!', 4096), 0, str_repeat('A%20z%21', 4096)),
);
foreach ($cases as $index => $case) {
    $actual = filter_var($case[0], FILTER_SANITIZE_ENCODED, $case[1]);
    if ($actual !== $case[2]) {
        echo 'ordinary case ', $index, " failed\n";
        $failures++;
    }
}
echo 'failures=', $failures, "\n";
?>
--EXPECT--
failures=0
