"""Independent literal expected maps for benign synthetic names/values.

HTTP decoding is performed by PHP in the real FPM campaign. The C adapter's
registration tokens are an explicit wire-decoding model, not that parser.
"""


def cases():
    rows=[]
    def add(name,cookie,form,pc,cc,pf=None,cf=None):
        rows.append(dict(name=name,cookie=cookie,form=form,parent={'C':pc,'G':pc if pf is None else pf,'P':pc if pf is None else pf},
                         candidate={'C':cc,'G':cc if cf is None else cf,'P':cc if cf is None else cf}))
    for tag in ('Host','Secure'):
        key='__'+tag+'-demo'
        add('dot-'+tag.lower(),'._'+tag+'-demo=demo','._'+tag+'-demo=demo',{key:'demo'},{})
        add('fallback-'+tag.lower(),'_['+tag+'-demo=demo','_['+tag+'-demo=demo',{key:'demo'},{})
        add('indexed-'+tag.lower(),'._'+tag+'-demo[x]=demo','._'+tag+'-demo[x]=demo',{key:{'x':'demo'}},{})
    add('nested-prefix','prefs[__Host-nested]=demo','prefs[__Host-nested]=demo',{'prefs':{'__Host-nested':'demo'}},{'prefs':{}})
    auth={'__Host-demo':'legit','__Secure-demo':'legit'}
    add('authentic','__Host-demo=legit; __Secure-demo=legit','__Host-demo=legit&__Secure-demo=legit',auth,auth)
    auth_array={'__Host-demo':{'x':'legit'},'__Secure-demo':{0:'one',1:'two'}}
    add('authentic-array','__Host-demo[x]=legit;__Secure-demo[]=one;__Secure-demo[]=two','__Host-demo[x]=legit&__Secure-demo[]=one&__Secure-demo[]=two',auth_array,auth_array)
    normal={'plain':'one','a_b':'two','arr':{'x':'last'},'list':{0:'a',1:'b'},'num':{'01':'p',0:'z'}}
    add('normal-array','plain=one;a.b=two;arr[x]=first;arr[x]=last;list[]=a;list[]=b;num[01]=p;num[0]=z','plain=one&a.b=two&arr[x]=first&arr[x]=last&list[]=a&list[]=b&num[01]=p&num[0]=z',normal,normal)
    first={'dup':'first','__Host-demo':'first'};last={'dup':'last','__Host-demo':'last'}
    add('duplicates','dup=first;dup=last;__Host-demo=first;__Host-demo=last','dup=first&dup=last&__Host-demo=first&__Host-demo=last',first,first,last,last)
    add('bad-then-authentic','._Host-demo=untrusted;__Host-demo=trusted','._Host-demo=untrusted&__Host-demo=trusted',{'__Host-demo':'untrusted'},{'__Host-demo':'trusted'},{'__Host-demo':'trusted'},{'__Host-demo':'trusted'})
    add('authentic-then-bad','__Host-demo=trusted;._Host-demo=untrusted','__Host-demo=trusted&._Host-demo=untrusted',{'__Host-demo':'trusted'},{'__Host-demo':'trusted'},{'__Host-demo':'untrusted'},{'__Host-demo':'trusted'})
    literal={'%5F%5FHost-demo':'literal','arr%5Bx%5D':'value'};decoded={'__Host-demo':'literal','arr':{'x':'value'}}
    add('cookie-name-not-decoded','%5F%5FHost-demo=literal;arr%5Bx%5D=value','%5F%5FHost-demo=literal&arr%5Bx%5D=value',literal,literal,decoded,decoded)
    suffix={'__Host-demo_x':'ok'};add('authentic-suffix','__Host-demo.x=ok','__Host-demo.x=ok',suffix,suffix)
    leading={'plain':'one','__Host-demo':'ok'};add('leading-space',' plain=one; __Host-demo=ok','plain=one&%20%20__Host-demo=ok',leading,leading)
    short={'_':'one','__':'two','__Host':'three','__Secure':'four'}
    add('short-prefix','_=one;__=two;__Host=three;__Secure=four','_=one&__=two&__Host=three&__Secure=four',short,short)
    binary={'plain':'A\x00B','plus':'one two'};add('binary-values','plain=A%00B;plus=one+two','plain=A%00B&plus=one+two',binary,binary)
    add('normal-alias-duplicate','a.b=first;a_b=last','a.b=first&a_b=last',{'a_b':'first'},{'a_b':'first'},{'a_b':'last'},{'a_b':'last'})
    return rows


def flatten(mapping,prefix=''):
    out={}
    for key,value in mapping.items():
        segment='I'+str(key) if isinstance(key,int) else 'S'+key.encode().hex()
        path=prefix+'/'+segment if prefix else segment
        out[path]='A' if isinstance(value,dict) else 'V'+value.encode().hex()
        if isinstance(value,dict):out.update(flatten(value,path))
    return out

