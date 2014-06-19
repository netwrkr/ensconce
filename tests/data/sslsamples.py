from collections import namedtuple

KeyPair = namedtuple('KeyPair', ['cert', 'key'])

_s1_key = """-----BEGIN RSA PRIVATE KEY-----
MIIEpAIBAAKCAQEA36SYAfM+loQFm4OvBIARgXy39hew3D8uVxiZYjU1kmH9FLMZ
6Q7CGd0omBSGgeui/V6WP6kQERsmoIMKbJagPOTwf9Q0rCj5xTHAXZcTqcPT6HJ9
4iXb22OaP46nWGGqE5h8j7blHdNmkZOVTDoNDdFsGyOkZeXZhBYgO6OivKPz0nSV
rf5uEFap44QgrMq9lyljK18Us9OpR4Xs0PoGfzerXV/JQ1/oSll6+y3XCpFzawlw
9LWmwkAVzAlFlGx2HLfNV0h8kbH4tWsCEDwEm/WObPWBlmJWlHVYjH35FV6TUp7X
K9XKEovUO0Hb5gM4RYceUEBToSsg/2lsVn9RBQIDAQABAoIBAEEvWlcHLTD13iSL
51Fqeq/BSGVkVlp71+fu9ZYYaDr4cKm94kl50b10JsbdBK+NnP44uZZokpRJ06Jp
T3qDFMVq/WZk1c1wTAzcCXO9+y86MuPHq0VlP4XcrDLmQ4SRQt9fTL8e0f01hunb
mGKVcQScC+SFKP/CVPoY8OAxO9e7bnJ7V0b6aeTNSv85OdKOOHSOOAC1dFKpZm8p
E50BjOr9qkYSD27q0RkwgG+MvbgKOOzs39a8fclMkv23H6GEXAq1+T9Igh9WswJg
KZRbBYWSpiX+fXAP9I13D1Y4O7H+uxV7kPVA5Do31BCzZ86diiivXc8GcEUHPxiQ
pgOwu2kCgYEA8Vk8DfrM+OxZrB1zZgEEGYXnE+FewPyptdE/WGryIkN60JilZlTZ
+JYucOiV0T2GfaDkhhAfa8sRMU9KM5WSa1QK4ZALw7PC85dINA7+ZtyxieJdUlib
5VRyQiZ+/y8QFGz1VEhfPapdrhbdJcTz8mV73hfEnIvpA5dYuBp/lvsCgYEA7Tgy
zB/+HgNTYbCsVg29+EYGqh0V/0hxQqilX4p+qKRYB509+KtuRMcmfN8I9JwFIX2f
esd5TWi+orwHIHX3bLWeNNrA3wmBTwb9JXwE9I49ZqkI37wbq1BrxWhw3YL+eQ0U
05Uy7iT01uCPlxcmsFXnusmlx35xC8yU6vZoN/8CgYEAtnPHOqpHGkdS4xLAknRi
LQlVT2oov6xCf/jX8nem5NAuoFNFdr7eqVafdSvfVnc0nPRszgySNGMndCeE6MpC
DnFSaIME4cWbs5rCMtjC6fAdJyfBdOcXs57LYcbIaxGhDk/whu7PUUbh2yHdvRfP
c4fUxGkjcVUzqktX/pXJrtECgYEA6FgI+QHE5iSfwKlIwqiHDuuXj3sZloaf2IhS
IbgGwqrlRd/vWOagBGGDAv95SAygweLHF3zVBMq5Ha9I07R3eVSR9nbkPhCTRJI1
1Ecam2XOIgUiGfGmsC7+v8XB9lRdZrc3VN1nmvU7klM0kOouDLy3Ua4735+qncHt
gg2CmoUCgYAzcg9PHGVBlpvvQ7xgUNNhLAsf5b6t6GRZVwwWl0X/xzEpxniumxQj
Jb0FLnL+svky1KIrcUJpEi5rqgaag7kRkifIG/oC15pkWffxz5nrQbhvDDvVBgen
MZFnBnD103MmrjnbSD51iLdUVEXReXAzN/eDuMUKkhmK3DJ1XG44GA==
-----END RSA PRIVATE KEY-----
"""

_s1_cert = """-----BEGIN CERTIFICATE-----
MIIDNDCCAhwCCQCPT4neBDCsfDANBgkqhkiG9w0BAQUFADBcMQswCQYDVQQGEwJY
WDEVMBMGA1UEBwwMRGVmYXVsdCBDaXR5MRwwGgYDVQQKDBNEZWZhdWx0IENvbXBh
bnkgTHRkMRgwFgYDVQQDDA9vbmUuZXhhbXBsZS5jb20wHhcNMTMwMTI4MTIzMTE5
WhcNMjMwMTI2MTIzMTE5WjBcMQswCQYDVQQGEwJYWDEVMBMGA1UEBwwMRGVmYXVs
dCBDaXR5MRwwGgYDVQQKDBNEZWZhdWx0IENvbXBhbnkgTHRkMRgwFgYDVQQDDA9v
bmUuZXhhbXBsZS5jb20wggEiMA0GCSqGSIb3DQEBAQUAA4IBDwAwggEKAoIBAQDf
pJgB8z6WhAWbg68EgBGBfLf2F7DcPy5XGJliNTWSYf0UsxnpDsIZ3SiYFIaB66L9
XpY/qRARGyaggwpslqA85PB/1DSsKPnFMcBdlxOpw9Pocn3iJdvbY5o/jqdYYaoT
mHyPtuUd02aRk5VMOg0N0WwbI6Rl5dmEFiA7o6K8o/PSdJWt/m4QVqnjhCCsyr2X
KWMrXxSz06lHhezQ+gZ/N6tdX8lDX+hKWXr7LdcKkXNrCXD0tabCQBXMCUWUbHYc
t81XSHyRsfi1awIQPASb9Y5s9YGWYlaUdViMffkVXpNSntcr1coSi9Q7QdvmAzhF
hx5QQFOhKyD/aWxWf1EFAgMBAAEwDQYJKoZIhvcNAQEFBQADggEBAFHMXMpLczdv
LB7SafPx3I383evP0ZT2tNVgoRfHgSAsdd7igQaaGZvwIykFTYyzB/lqpr73HumT
bFv1Naq4eLnrdjE9dpbHec9ZTQOen0wGNcChKdZ2ahHaUXlLHJM4qLJPTq6XUO+D
YB6/ehJIQ3qV+X7KOpBvWNBD5GSXLjPQJhikPZBFZyJvoBSRPZRersehqgNTACEI
uIOEvTJBRlR0cyTcyKo/AlFP75kildnrrsLVDWTASCsbdc6N1qPGVJcy/uD95RVi
WzfhoklnkloRNQhWNFOjhy3CfLEoMpVieKTsHTeR4iSrdLfTe0pAiagca/IS6cAw
uLEeO37uiBE=
-----END CERTIFICATE-----
"""

keypair1 = KeyPair(cert=_s1_cert, key=_s1_key)