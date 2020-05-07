# """CLI for gogogate device."""
# from enum import Enum
# import pprint
#
# from gogogate2_api import GogoGate2Api
#
#
# def isnamedtupleinstance(x):
#     _type = type(x)
#     bases = _type.__bases__
#     if len(bases) != 1 or bases[0] != tuple:
#         return False
#     fields = getattr(_type, "_fields", None)
#     if not isinstance(fields, tuple):
#         return False
#     return all(type(i) == str for i in fields)
#
#
# def unpack(obj):
#     if isinstance(obj, dict):
#         return {key: unpack(value) for key, value in obj.items()}
#     elif isinstance(obj, list):
#         return [unpack(value) for value in obj]
#     elif isnamedtupleinstance(obj):
#         return {key: unpack(value) for key, value in obj._asdict().items()}
#     elif isinstance(obj, tuple):
#         return tuple(unpack(value) for value in obj)
#     elif isinstance(obj, Enum):
#         return obj.value
#     else:
#         return obj
#
#
# def main() -> None:
#     pretty_print = pprint.PrettyPrinter(indent=4)
#     # API = GogoGate2Api("10.40.11.84", "admin", "4ZsdV9A4s0zhkp3%KoYQVXe$B$")
#     api = GogoGate2Api("10.40.3.157", "admin", "OJa$52OaeSVA&b9W9WsR&yq!L1")
#     # response = api.info()
#     response = api.activate(11)
#     # api._request("activate", 2, "FFFFF")
#     # print('RRR', response)
#     # print(type(unpack(response)))
#     pretty_print.pprint(unpack(response))
#
#
# main()
