--TEST--
Cookie-prefix provenance and shared parse_str registration regressions
--FILE--
<?php

function emit_tree($kind,$values,$prefix='') {
    foreach($values as $key=>$value) {
        $segment=is_int($key)?'I'.$key:'S'.bin2hex($key);
        $path=$prefix===''?$segment:$prefix.'/'.$segment;
        echo $kind,'|',$path,'=',is_array($value)?'A':'V'.bin2hex($value),"\n";
        if(is_array($value)){emit_tree($kind,$value,$path);}
    }
}
echo 'BEGIN=dot-host',"\n";
parse_str('._Host-demo=demo',$values);emit_tree('G',$values);
echo 'END=dot-host',"\n";
echo 'BEGIN=fallback-host',"\n";
parse_str('_[Host-demo=demo',$values);emit_tree('G',$values);
echo 'END=fallback-host',"\n";
echo 'BEGIN=indexed-host',"\n";
parse_str('._Host-demo[x]=demo',$values);emit_tree('G',$values);
echo 'END=indexed-host',"\n";
echo 'BEGIN=dot-secure',"\n";
parse_str('._Secure-demo=demo',$values);emit_tree('G',$values);
echo 'END=dot-secure',"\n";
echo 'BEGIN=fallback-secure',"\n";
parse_str('_[Secure-demo=demo',$values);emit_tree('G',$values);
echo 'END=fallback-secure',"\n";
echo 'BEGIN=indexed-secure',"\n";
parse_str('._Secure-demo[x]=demo',$values);emit_tree('G',$values);
echo 'END=indexed-secure',"\n";
echo 'BEGIN=nested-prefix',"\n";
parse_str('prefs[__Host-nested]=demo',$values);emit_tree('G',$values);
echo 'END=nested-prefix',"\n";
echo 'BEGIN=authentic',"\n";
parse_str('__Host-demo=legit&__Secure-demo=legit',$values);emit_tree('G',$values);
echo 'END=authentic',"\n";
echo 'BEGIN=authentic-array',"\n";
parse_str('__Host-demo[x]=legit&__Secure-demo[]=one&__Secure-demo[]=two',$values);emit_tree('G',$values);
echo 'END=authentic-array',"\n";
echo 'BEGIN=normal-array',"\n";
parse_str('plain=one&a.b=two&arr[x]=first&arr[x]=last&list[]=a&list[]=b&num[01]=p&num[0]=z',$values);emit_tree('G',$values);
echo 'END=normal-array',"\n";
echo 'BEGIN=duplicates',"\n";
parse_str('dup=first&dup=last&__Host-demo=first&__Host-demo=last',$values);emit_tree('G',$values);
echo 'END=duplicates',"\n";
echo 'BEGIN=bad-then-authentic',"\n";
parse_str('._Host-demo=untrusted&__Host-demo=trusted',$values);emit_tree('G',$values);
echo 'END=bad-then-authentic',"\n";
echo 'BEGIN=authentic-then-bad',"\n";
parse_str('__Host-demo=trusted&._Host-demo=untrusted',$values);emit_tree('G',$values);
echo 'END=authentic-then-bad',"\n";
echo 'BEGIN=cookie-name-not-decoded',"\n";
parse_str('%5F%5FHost-demo=literal&arr%5Bx%5D=value',$values);emit_tree('G',$values);
echo 'END=cookie-name-not-decoded',"\n";
echo 'BEGIN=authentic-suffix',"\n";
parse_str('__Host-demo.x=ok',$values);emit_tree('G',$values);
echo 'END=authentic-suffix',"\n";
echo 'BEGIN=leading-space',"\n";
parse_str('plain=one&%20%20__Host-demo=ok',$values);emit_tree('G',$values);
echo 'END=leading-space',"\n";
echo 'BEGIN=short-prefix',"\n";
parse_str('_=one&__=two&__Host=three&__Secure=four',$values);emit_tree('G',$values);
echo 'END=short-prefix',"\n";
echo 'BEGIN=binary-values',"\n";
parse_str('plain=A%00B&plus=one+two',$values);emit_tree('G',$values);
echo 'END=binary-values',"\n";
echo 'BEGIN=normal-alias-duplicate',"\n";
parse_str('a.b=first&a_b=last',$values);emit_tree('G',$values);
echo 'END=normal-alias-duplicate',"\n";
--EXPECT--
BEGIN=dot-host
END=dot-host
BEGIN=fallback-host
END=fallback-host
BEGIN=indexed-host
END=indexed-host
BEGIN=dot-secure
END=dot-secure
BEGIN=fallback-secure
END=fallback-secure
BEGIN=indexed-secure
END=indexed-secure
BEGIN=nested-prefix
G|S7072656673=A
END=nested-prefix
BEGIN=authentic
G|S5f5f486f73742d64656d6f=V6c65676974
G|S5f5f5365637572652d64656d6f=V6c65676974
END=authentic
BEGIN=authentic-array
G|S5f5f486f73742d64656d6f=A
G|S5f5f486f73742d64656d6f/S78=V6c65676974
G|S5f5f5365637572652d64656d6f=A
G|S5f5f5365637572652d64656d6f/I0=V6f6e65
G|S5f5f5365637572652d64656d6f/I1=V74776f
END=authentic-array
BEGIN=normal-array
G|S706c61696e=V6f6e65
G|S615f62=V74776f
G|S617272=A
G|S617272/S78=V6c617374
G|S6c697374=A
G|S6c697374/I0=V61
G|S6c697374/I1=V62
G|S6e756d=A
G|S6e756d/S3031=V70
G|S6e756d/I0=V7a
END=normal-array
BEGIN=duplicates
G|S647570=V6c617374
G|S5f5f486f73742d64656d6f=V6c617374
END=duplicates
BEGIN=bad-then-authentic
G|S5f5f486f73742d64656d6f=V74727573746564
END=bad-then-authentic
BEGIN=authentic-then-bad
G|S5f5f486f73742d64656d6f=V74727573746564
END=authentic-then-bad
BEGIN=cookie-name-not-decoded
G|S5f5f486f73742d64656d6f=V6c69746572616c
G|S617272=A
G|S617272/S78=V76616c7565
END=cookie-name-not-decoded
BEGIN=authentic-suffix
G|S5f5f486f73742d64656d6f5f78=V6f6b
END=authentic-suffix
BEGIN=leading-space
G|S706c61696e=V6f6e65
G|S5f5f486f73742d64656d6f=V6f6b
END=leading-space
BEGIN=short-prefix
G|S5f=V6f6e65
G|S5f5f=V74776f
G|S5f5f486f7374=V7468726565
G|S5f5f536563757265=V666f7572
END=short-prefix
BEGIN=binary-values
G|S706c61696e=V410042
G|S706c7573=V6f6e652074776f
END=binary-values
BEGIN=normal-alias-duplicate
G|S615f62=V6c617374
END=normal-alias-duplicate
