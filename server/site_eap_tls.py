# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime, logging, re, subprocess, os

# These certificate trees are for testing only in sealed containers
# so it is okay that we have them checked into a GIT repository.
# Nobody will ever use this information on the open air.

cert_info = {
    'cert1': {
        'router': {
            'ca_cert':
"""-----BEGIN CERTIFICATE-----
MIIDMTCCApqgAwIBAgIJANAMhNy2leWKMA0GCSqGSIb3DQEBBQUAMG8xCzAJBgNV
BAYTAlVTMRMwEQYDVQQIEwpDYWxpZm9ybmlhMRYwFAYDVQQHEw1Nb3VudGFpbiBW
aWV3MTMwMQYDVQQDEypjaHJvbWVsYWItd2lmaS10ZXN0YmVkLXJvb3QubXR2Lmdv
b2dsZS5jb20wHhcNMTAwODExMDAyODI3WhcNMjAwODA4MDAyODI3WjBvMQswCQYD
VQQGEwJVUzETMBEGA1UECBMKQ2FsaWZvcm5pYTEWMBQGA1UEBxMNTW91bnRhaW4g
VmlldzEzMDEGA1UEAxMqY2hyb21lbGFiLXdpZmktdGVzdGJlZC1yb290Lm10di5n
b29nbGUuY29tMIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQDKzIZQXJjjtuQO
hQvHUa436mSOSo7PTP4cM39Ip7dlSRqTL+lHdQN9d0dgrYQFvlHwaG5CBVYhtFtQ
JMy2ozauwTwtD5oHHL0DyhhgNA9H4zrTpM/t5euHpZwrOik7lnw87JBdKto/wy5X
bhKOwvrRSsJIVLc2j5bD0225EPff6wIDAQABo4HUMIHRMB0GA1UdDgQWBBRw5Wl2
YFf67mTeir0yYaF/jUS9QTCBoQYDVR0jBIGZMIGWgBRw5Wl2YFf67mTeir0yYaF/
jUS9QaFzpHEwbzELMAkGA1UEBhMCVVMxEzARBgNVBAgTCkNhbGlmb3JuaWExFjAU
BgNVBAcTDU1vdW50YWluIFZpZXcxMzAxBgNVBAMTKmNocm9tZWxhYi13aWZpLXRl
c3RiZWQtcm9vdC5tdHYuZ29vZ2xlLmNvbYIJANAMhNy2leWKMAwGA1UdEwQFMAMB
Af8wDQYJKoZIhvcNAQEFBQADgYEAZAiBupvbckbb9ICASaz0a1uE4VNSqAZhhBXm
AmrjmwnYU+yFkGgscyoq6wLzA+VbbfeBo088GT1LTyzUFqnsLNk7NrT1dtuCPijS
p8gKkMu03kpkoKO0H9OB7HMRcdB7O87c5S1de4PLqdTwooF0f+yT6dqivUHgP5KF
K3F2V44=
-----END CERTIFICATE-----""",
            'server_cert':
"""-----BEGIN CERTIFICATE-----
MIIDPTCCAqagAwIBAgIDEAABMA0GCSqGSIb3DQEBBAUAMG8xCzAJBgNVBAYTAlVT
MRMwEQYDVQQIEwpDYWxpZm9ybmlhMRYwFAYDVQQHEw1Nb3VudGFpbiBWaWV3MTMw
MQYDVQQDEypjaHJvbWVsYWItd2lmaS10ZXN0YmVkLXJvb3QubXR2Lmdvb2dsZS5j
b20wHhcNMTAwODExMDAyODI3WhcNMTEwODExMDAyODI3WjBxMQswCQYDVQQGEwJV
UzETMBEGA1UECBMKQ2FsaWZvcm5pYTEWMBQGA1UEBxMNTW91bnRhaW4gVmlldzE1
MDMGA1UEAxMsY2hyb21lbGFiLXdpZmktdGVzdGJlZC1zZXJ2ZXIubXR2Lmdvb2ds
ZS5jb20wgZ8wDQYJKoZIhvcNAQEBBQADgY0AMIGJAoGBAPn4bKRL1o6E0V9346pa
ZNmeVujp8L6gIxk1z5cFDcs07K7XV4ML/M2GPaYuHFGYgs5PO29Bju/oG246kI/o
n7uEEcVedXWYOuQL+W3QI7c6NYsAiQmMSpLRlqX9q0QCAMXs/Hipm0oKGYA5Tsdo
q9UIszkOIhZHP+YPbkJFyrATAgMBAAGjgeQwgeEwCQYDVR0TBAIwADARBglghkgB
hvhCAQEEBAMCBkAwHQYDVR0OBBYEFDYGlkJwDwKS0M4/SYFdTlLDcvsBMIGhBgNV
HSMEgZkwgZaAFHDlaXZgV/ruZN6KvTJhoX+NRL1BoXOkcTBvMQswCQYDVQQGEwJV
UzETMBEGA1UECBMKQ2FsaWZvcm5pYTEWMBQGA1UEBxMNTW91bnRhaW4gVmlldzEz
MDEGA1UEAxMqY2hyb21lbGFiLXdpZmktdGVzdGJlZC1yb290Lm10di5nb29nbGUu
Y29tggkA0AyE3LaV5YowDQYJKoZIhvcNAQEEBQADgYEAQphT8fiEPvwuDpzkuClg
xqajzKwX677ggbYrP+k1v2WIPRBUW7lZs8OdKgwkIxvD4RBNwztEcBreWJG0I5xQ
sJ9H+K12INdQ+TOrSAiEYuy4bu9EXf2On7MsAgcSTbQHN3bLuvtag3frDVvERlMU
iaHwTA/p/X5zeCxKQunfwP0=
-----END CERTIFICATE-----""",
            'private_key':
"""-----BEGIN RSA PRIVATE KEY-----
MIICXAIBAAKBgQD5+GykS9aOhNFfd+OqWmTZnlbo6fC+oCMZNc+XBQ3LNOyu11eD
C/zNhj2mLhxRmILOTztvQY7v6BtuOpCP6J+7hBHFXnV1mDrkC/lt0CO3OjWLAIkJ
jEqS0Zal/atEAgDF7Px4qZtKChmAOU7HaKvVCLM5DiIWRz/mD25CRcqwEwIDAQAB
AoGBAPWF55f8kXKMzGXcCTdC8Dm7x5ugZIGoIrFZZFvub9z/T9Zv1xn1hUqNpzH5
qoEOrrRbqIIfv3iu33qGdYWUNIZ2PO/9q/IQ31Z4eV2iVQ3kpjoZnvfhyJ7t0QXG
xbS1F5UAcS1cdVxPjWkXYg4uoIg3/Y+HCW6n77v8UPl0+QT5AkEA/1XfTVYqs6eI
I7pNip+tqwFg93WewZ4it17O1VxaSZX+rjLs6+nxzVeWyIAcbw5Tdos4onafsf8t
ncjrqB0ebQJBAPqe+jk97pazkSKqIyXogpApZ1EbJHHJblS4HU/FAq0wZHMqvDmy
8sQR+B7RZ96MnuIGsVIbKz0BveuD+wn7+H8CQHl9k32JxVGsIiPVznVqGskmI8w6
4+n+Y0hazRFKGw+uVfru8joiG1J4HZ+TDXRuHZpnDfCHft7DqyHLaw2XpVUCQCGW
UrR/L011DTtXD9TRv0Wwts7w00aIl0e1UQBSx9QMCzo//O/CorRSMC15JPF3aQej
m/oD+Bx58kjw7CDfauMCQGV7dPtWmA6DbparS8Z59Fx25XpN6+asw+Krrq3iGqpf
/E8LtHSUdiUZztQN0oUUCEh8C//2NRDUK5M2Y7kjF+Y=
-----END RSA PRIVATE KEY-----""",
            'eap_user_file': '* TLS'
        },
        'client': {
            'client_cert':
"""-----BEGIN CERTIFICATE-----
MIIDKjCCApOgAwIBAgIDEAACMA0GCSqGSIb3DQEBBAUAMG8xCzAJBgNVBAYTAlVT
MRMwEQYDVQQIEwpDYWxpZm9ybmlhMRYwFAYDVQQHEw1Nb3VudGFpbiBWaWV3MTMw
MQYDVQQDEypjaHJvbWVsYWItd2lmaS10ZXN0YmVkLXJvb3QubXR2Lmdvb2dsZS5j
b20wHhcNMTAwODExMDAyODMwWhcNMTEwODExMDAyODMwWjBxMQswCQYDVQQGEwJV
UzETMBEGA1UECBMKQ2FsaWZvcm5pYTEWMBQGA1UEBxMNTW91bnRhaW4gVmlldzE1
MDMGA1UEAxMsY2hyb21lbGFiLXdpZmktdGVzdGJlZC1jbGllbnQubXR2Lmdvb2ds
ZS5jb20wgZ8wDQYJKoZIhvcNAQEBBQADgY0AMIGJAoGBAJu8uIlc6Ags6KS2bwqO
flfILS//9YHJ/ch5GIC6PjA9HCUFlQSVuUb+igZ/CLZ+mTEiC76xVUD5GgZdJdHb
lX0uTC6dI1N42pOklBNl3S3uXXyNGk1Ztg+6Lom/VKw1srlIKHIT/iMVYtzbt3+q
hXOEjSMbMQb2hivwwV5kQSdDAgMBAAGjgdEwgc4wCQYDVR0TBAIwADAdBgNVHQ4E
FgQUMGYODAgMy1ohCO7Aau20Zw3lSO8wgaEGA1UdIwSBmTCBloAUcOVpdmBX+u5k
3oq9MmGhf41EvUGhc6RxMG8xCzAJBgNVBAYTAlVTMRMwEQYDVQQIEwpDYWxpZm9y
bmlhMRYwFAYDVQQHEw1Nb3VudGFpbiBWaWV3MTMwMQYDVQQDEypjaHJvbWVsYWIt
d2lmaS10ZXN0YmVkLXJvb3QubXR2Lmdvb2dsZS5jb22CCQDQDITctpXlijANBgkq
hkiG9w0BAQQFAAOBgQAqUk+8N8NLGnLvNdRXYG2krhptGHO9h0YHjOh+xxOUcBis
DiSKG0/M5ucqGOJmF5DTDNVCLkjOcd69Zv+a/eFohlZ4K3rWo0vQs77e9rtkepB1
N+6M3dMP8Z9dhfgUp3ha84mSBY6qguNFKzSUZsBQ6JF5xxhjBRHP/5t/Sz2k2A==
-----END CERTIFICATE-----""",
            'private_key':
"""-----BEGIN RSA PRIVATE KEY-----
MIICXQIBAAKBgQCbvLiJXOgILOiktm8Kjn5XyC0v//WByf3IeRiAuj4wPRwlBZUE
lblG/ooGfwi2fpkxIgu+sVVA+RoGXSXR25V9LkwunSNTeNqTpJQTZd0t7l18jRpN
WbYPui6Jv1SsNbK5SChyE/4jFWLc27d/qoVzhI0jGzEG9oYr8MFeZEEnQwIDAQAB
AoGBAJk2qinhcBkS7XGWVVoCY8PCmMofO44LhZQjpnqGP8Y/aJ/3hOp0zklNA8du
VMkNdXLD9uANID2ClBrsqtdx+vcac+mPSjxwI+tszVIzKHesYMf9XJJQrtP6gl4o
sA6YOQB65dhYLpckuR4vb28Dwo2W8Ha4lv/zzeCo9/LOOm5hAkEAzegQGCnAdeui
OShVZ69IcPJLMbZt641yeghWiBvclQxtvXk77Wf3jDoi16XqhGhvhkJRqcoUg+zg
zwxFr6RqEwJBAMGgGBMPqNDtVS4pGcsr0xI8hIsDsSEBtlvfwpt1BeVJKdooQ51c
gDK7Q28MV/xtrvlvo2J1Slod/6sZ681U9BECQQCToBzh5hVZth4x0qwg0XgjmmO0
+bGnX1tDCPVZUnh82FNZtDD2DkNaY1gVupwAYIwM+0FndT3uNAgeChNwUXXHAkBB
gkXC5TBrh3CjTnqQl8Iw0FLTqasbDLZC/UCdUgltmsRTL/44Vlx1TZAyGQ4HtKBX
eiLgI+jE9pNSs1FpRg3RAkBAxoAqiYyT9W222119Qt6PdJDTNI/YxKpDfnwRZm84
7x3V0FVuaN1GW9g4VMSsearlmgYizfRliaIrD+15Bg9Q
-----END RSA PRIVATE KEY-----""",
        }
    },


    'cert2': {
        'router': {
            'ca_cert':
"""-----BEGIN CERTIFICATE-----
MIIDNDCCAp2gAwIBAgIJAPCOBeiGsMUzMA0GCSqGSIb3DQEBBQUAMHAxCzAJBgNV
BAYTAlVTMRMwEQYDVQQIEwpDYWxpZm9ybmlhMRYwFAYDVQQHEw1Nb3VudGFpbiBW
aWV3MTQwMgYDVQQDEytjaHJvbWVsYWItd2lmaS10ZXN0YmVkMi1yb290Lm10di5n
b29nbGUuY29tMB4XDTEwMTAxMTIxMTM1OFoXDTIwMTAwODIxMTM1OFowcDELMAkG
A1UEBhMCVVMxEzARBgNVBAgTCkNhbGlmb3JuaWExFjAUBgNVBAcTDU1vdW50YWlu
IFZpZXcxNDAyBgNVBAMTK2Nocm9tZWxhYi13aWZpLXRlc3RiZWQyLXJvb3QubXR2
Lmdvb2dsZS5jb20wgZ8wDQYJKoZIhvcNAQEBBQADgY0AMIGJAoGBALVcrIDKH5KL
anHb9qBxI78GA/CxyevvmkUL862xVwWFWedwCFxCYLUeNW5v1GLU1Nlq/8Yp1Kit
pDMqkgHwhFZheT+cU2CXBHrjCp4csaaZSgEnvDjfgFHwwjf/ghtFgaF+0YgmNm2u
lClPs/Ar4Ed/xonR3djtPuadqqodl6h3AgMBAAGjgdUwgdIwHQYDVR0OBBYEFMTK
tCdJf+j7+/ORDIDna9dgIV/SMIGiBgNVHSMEgZowgZeAFMTKtCdJf+j7+/ORDIDn
a9dgIV/SoXSkcjBwMQswCQYDVQQGEwJVUzETMBEGA1UECBMKQ2FsaWZvcm5pYTEW
MBQGA1UEBxMNTW91bnRhaW4gVmlldzE0MDIGA1UEAxMrY2hyb21lbGFiLXdpZmkt
dGVzdGJlZDItcm9vdC5tdHYuZ29vZ2xlLmNvbYIJAPCOBeiGsMUzMAwGA1UdEwQF
MAMBAf8wDQYJKoZIhvcNAQEFBQADgYEAOcPgWGaHVj/UZBFOV3QutkNb/tsvHFEX
xVn641V1gw52jVHvM+DFhXmoRjk9JTgT0g6ALj10ehw0zOI0jxV27x30sLRE+op7
t++4i/fcz1VvuwhFxDRXjoY8BO+1lYUOtsapRHHASZvU1Wf+AhO2N9xtvlckFxpS
wK+1l98+x4o=
-----END CERTIFICATE-----""",
            'server_cert':
"""-----BEGIN CERTIFICATE-----
MIIDQDCCAqmgAwIBAgIDEAABMA0GCSqGSIb3DQEBBAUAMHAxCzAJBgNVBAYTAlVT
MRMwEQYDVQQIEwpDYWxpZm9ybmlhMRYwFAYDVQQHEw1Nb3VudGFpbiBWaWV3MTQw
MgYDVQQDEytjaHJvbWVsYWItd2lmaS10ZXN0YmVkMi1yb290Lm10di5nb29nbGUu
Y29tMB4XDTEwMTAxMTIxMTM1OFoXDTExMTAxMTIxMTM1OFowcjELMAkGA1UEBhMC
VVMxEzARBgNVBAgTCkNhbGlmb3JuaWExFjAUBgNVBAcTDU1vdW50YWluIFZpZXcx
NjA0BgNVBAMTLWNocm9tZWxhYi13aWZpLXRlc3RiZWQyLXNlcnZlci5tdHYuZ29v
Z2xlLmNvbTCBnzANBgkqhkiG9w0BAQEFAAOBjQAwgYkCgYEAzP5YdymNCXBlhlD5
mK5Mm9H3pG+8fLx7oIKvKea3DZ8yjGd/QK8jMo4EWccFY+jI3pjwO7gmI6ntlU5y
bCL+29GPbjRtoA9zvVmD01ggGEDW+rJVKIUALPlCT/85jcwDHSzqQt9Gpj576oP5
y/nv4iEkJzmryZv46pGxtnxW6aUCAwEAAaOB5TCB4jAJBgNVHRMEAjAAMBEGCWCG
SAGG+EIBAQQEAwIGQDAdBgNVHQ4EFgQUJlQFb95atdqXA/Wtf5zd6PWA7AgwgaIG
A1UdIwSBmjCBl4AUxMq0J0l/6Pv785EMgOdr12AhX9KhdKRyMHAxCzAJBgNVBAYT
AlVTMRMwEQYDVQQIEwpDYWxpZm9ybmlhMRYwFAYDVQQHEw1Nb3VudGFpbiBWaWV3
MTQwMgYDVQQDEytjaHJvbWVsYWItd2lmaS10ZXN0YmVkMi1yb290Lm10di5nb29n
bGUuY29tggkA8I4F6IawxTMwDQYJKoZIhvcNAQEEBQADgYEAUQzJuYutS5Zi9DuI
CKVAyM7pR0poJkK33xwXT2Z3gMpQcNXO66omPdsoXi6aYt2Kmp3XJSAE2Ev+0EKQ
Lvu56jV19Sw4MBuF94Gd0Ts3Ps8/FB8yyQQ3f2qGWAYg4S37HsK+NIz5fsgzvW5X
tctFQRntW1evuf4y+hWaBtmpF8M=
-----END CERTIFICATE-----""",
            'private_key':
"""-----BEGIN RSA PRIVATE KEY-----
MIICXQIBAAKBgQDM/lh3KY0JcGWGUPmYrkyb0fekb7x8vHuggq8p5rcNnzKMZ39A
ryMyjgRZxwVj6MjemPA7uCYjqe2VTnJsIv7b0Y9uNG2gD3O9WYPTWCAYQNb6slUo
hQAs+UJP/zmNzAMdLOpC30amPnvqg/nL+e/iISQnOavJm/jqkbG2fFbppQIDAQAB
AoGAN7x0Gzo98bIQuJttsdi6VaeaOKh0zEmHJ5ZAwBjN7rM5UDmXvOOho04/2pUl
XwvdCcD1mJcyL4I1aeIhdEtzlZ5NOI1Y503Mrog6Fou6ui7WqB99msIZIxvbfLvG
mDhxd7HU+29MIZZfxdrvIgYIoZKY7V/s5hioX+7NSQsMfUUCQQDvPoEm4W4TyU9F
vMinZwIuCmk/FnHeSarZWtqxkSi5X/dQr7L8ko30lpMKjR2VljTYonHmBLPETjPU
FaDqLe/vAkEA21m/zdbVz4gPY0JtFyOhfnchSY6H/hQITz+IKbyCG3ovvYDIV7ZH
v7nsGhZd5J78yQJvKXfY63FpNynBos2rqwJBANZvaqljwxs/A6uZEyxgeqaztDPU
tUktNFJPSdeAKUVGS9DpOn+CCHSjBbaeV1b9Y+6MY5RswIgCJBhDLpDXjccCQD2f
3U8LCE6hvxD33IYfsINDHMr5jCNJpXv+MVboavUlQrxOrfpWb5nhtf8uQXq1X/dp
A6n2za530kN5K7l9ZrkCQQDkRew1VFDPg6baShXwEA327XH/0a/s3pSg3WNXaJ22
KKkkmvz0gVdObfCRIDf+Tw37tQ00n2hUUefuCnTnNFG/
-----END RSA PRIVATE KEY-----""",
            'eap_user_file': '* TLS'
        },
        'client': {
            'client_cert':
"""-----BEGIN CERTIFICATE-----
MIIDLTCCApagAwIBAgIDEAACMA0GCSqGSIb3DQEBBAUAMHAxCzAJBgNVBAYTAlVT
MRMwEQYDVQQIEwpDYWxpZm9ybmlhMRYwFAYDVQQHEw1Nb3VudGFpbiBWaWV3MTQw
MgYDVQQDEytjaHJvbWVsYWItd2lmaS10ZXN0YmVkMi1yb290Lm10di5nb29nbGUu
Y29tMB4XDTEwMTAxMTIxMTQwMFoXDTExMTAxMTIxMTQwMFowcjELMAkGA1UEBhMC
VVMxEzARBgNVBAgTCkNhbGlmb3JuaWExFjAUBgNVBAcTDU1vdW50YWluIFZpZXcx
NjA0BgNVBAMTLWNocm9tZWxhYi13aWZpLXRlc3RiZWQyLWNsaWVudC5tdHYuZ29v
Z2xlLmNvbTCBnzANBgkqhkiG9w0BAQEFAAOBjQAwgYkCgYEAum3Ffn32tAAotbva
R1yHQAb/eJ0agM7gkFD7ykTMxQgtvPaNJd1JOIrfzJkUJlkIO8Kw49L7J+yEwl/H
e4krWBU0H5AS/KgnFs37sUNbQSOuT2GxcJy/5ce3yTvKDx+bX8YBnqVgF/J4ftZg
k0Gw5bl8csL7ayMEPjQ67l6DmAECAwEAAaOB0jCBzzAJBgNVHRMEAjAAMB0GA1Ud
DgQWBBRVbfe54dvOd9N5S+z4QQBvxuwiHzCBogYDVR0jBIGaMIGXgBTEyrQnSX/o
+/vzkQyA52vXYCFf0qF0pHIwcDELMAkGA1UEBhMCVVMxEzARBgNVBAgTCkNhbGlm
b3JuaWExFjAUBgNVBAcTDU1vdW50YWluIFZpZXcxNDAyBgNVBAMTK2Nocm9tZWxh
Yi13aWZpLXRlc3RiZWQyLXJvb3QubXR2Lmdvb2dsZS5jb22CCQDwjgXohrDFMzAN
BgkqhkiG9w0BAQQFAAOBgQAG1VF/2QAD9bLOcRm8lpJflLDVJa9mv+p1p/c3liul
4djWyL2oQt4mWXuP8DNAXnuJVvSCOJFcSDlDZ3HTLYth8WUgkMwAdXO/mWpF74OS
8HikHuSK5oymkZB/AiQlnJlOY9nSLrEYQVLcvCfiJhhu+ziyDQlVawPIQqkBtX5y
qA==
-----END CERTIFICATE-----""",
            'private_key':
"""-----BEGIN RSA PRIVATE KEY-----
MIICXAIBAAKBgQC6bcV+ffa0ACi1u9pHXIdABv94nRqAzuCQUPvKRMzFCC289o0l
3Uk4it/MmRQmWQg7wrDj0vsn7ITCX8d7iStYFTQfkBL8qCcWzfuxQ1tBI65PYbFw
nL/lx7fJO8oPH5tfxgGepWAX8nh+1mCTQbDluXxywvtrIwQ+NDruXoOYAQIDAQAB
AoGAWzjDXnW8da9uPB7DXA/GjmneL+KPyV9xOqylx/+KQw8RclkiD9kLrwMlJzPw
TCNciAFoFNJz2sE85O+A6M3hys2dlXn/JR5I1IcVjkhOe6zaFu7btcRphbX/YqKi
+5oZj1rxBTEqhBXAKwIDkdF55A2a2Huq0eHIB/NA50Vw5hECQQDqqR4Iz+dGGufU
FywMoUgHjHW3iDjWgr+TF279k2BY5Fo03IDMIHFaNRT40hfFJFZh3t3hGe/RziJP
BRgnKikXAkEAy2HSHMuZuvaLAVkgKmUAdafnMkRCaCP4QlEHK98jix7KIyLApzaa
njuNW0jnUCI+4JTQxFlf4fn3h8Ugyn3GpwJBAIVb2TrO1LPNxKSPCrSez+2iUKAe
JZcbNT6l2aj4oY/DLtTN39CiO2k1s5Z455NdRE5YtyYfdGB60pqv3Xschb8CQCfM
z8pUyZO91XwBDftd4pYjsmmy0+//QgDwTF/4fcMm1lXD4kGWvPFEJCh9/s4+tWFL
ngMenlXhjeAi4oTd0jcCQBqIFwSDElqUqeqkMtlw14wEJH6XIk+0IVQndBEyb+JN
Nl40AoKFULXtQNMl7pT8uMj4ScYvRHOKg4RjwO7J+qs=
-----END RSA PRIVATE KEY-----""",
        }
    }
}

def insert_conf_file(host, filename, contents):
    """
    If config files are too big, the "host.run()" never returns.
    As a workaround, break the file up into lines and append the
    file piece by piece
    """
    host.run('rm -f %s >/dev/null 2>&1' % filename, ignore_status=True)
    content_lines = contents.splitlines()
    while content_lines:
        buflist = []
        buflen = 0
        while content_lines and buflen + len(content_lines[0]) < 200:
            line = content_lines.pop(0)
            buflen += len(line) + 1
            buflist.append(line)

        if not buflist:
            raise error.TestFail('Cert profile: line too long: %s' %
                                 content_lines[0])
        host.run('cat <<EOF >>%s\n%s\nEOF\n' %
                 (filename, '\n'.join(buflist)))

def router_config(router, cert):
    """
    Configure a router, and return the added config parameters
    """
    conf = {}
    # Make sure time-of-day is correct on router
    router.run('date -us %s' %
               datetime.datetime.utcnow().strftime('%Y%m%d%H%M.%S'))

    if cert not in cert_info:
        raise error.TestFail('Cert profile %s not in the configuration' % cert)

    for k, v in cert_info[cert]['router'].iteritems():
        filename = "/tmp/hostap_%s" % k
        insert_conf_file(router, filename, v)
        conf[k] = filename

    conf['eap_server'] = '1'
    return conf

def client_config(client, cert, ca_auth=None):
    """
    Configure a client, and return the added config parameters
    """
    if cert not in cert_info:
       raise error.TestFail("Cert profile %s not in the configuration" % cert)

    client_pkg = '/tmp/pkg-client.pem'
    info = cert_info[cert]['client']
    insert_conf_file(client, client_pkg,
                     '\n'.join([info['client_cert'], info['private_key']]))
    args = ['chromeos', client_pkg]
    if ca_auth:
        ca_cert = '/tmp/ca-cert.pem'
        cert_src = cert_info[ca_auth]['router']['ca_cert']
        insert_conf_file(client, ca_cert, cert_src)
        args.append(ca_cert)
    return { 'psk':  ':'.join(args) }
