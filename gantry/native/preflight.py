"""Report local installation prerequisites without launching an editor or consuming a license."""
import platform
from .catalog import PRODUCTS

CLASS_NAMES = {
    'solidworks': ('SldWorks.Application',),
    'catia-v5': ('CATIA.Application',),
    'creo': ('pfcls.CCpfcAsyncConnection', 'pfcls.CMpfcModelItem'),
    'solidworks-electrical': ('EwAPI.EwInteropFactoryX',),
}


def registration(name):
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, name + r'\CLSID') as key:
            value, _ = winreg.QueryValueEx(key, '')
            return 'registered' if value else 'missing'
    except FileNotFoundError:
        return 'missing'
    except OSError:
        return 'unknown'


def inspect_host():
    system = platform.system()
    rows = []
    for ident, (name, route, scope) in PRODUCTS.items():
        classes = {}
        if route == 'sdk_required':
            status = 'blocked_sdk'
        elif system != 'Windows':
            status = 'windows_host_required'
        elif route == 'direct':
            classes = {cls:registration(cls) for cls in CLASS_NAMES[ident]}
            status = 'registration_observed' if all(v == 'registered' for v in classes.values()) else 'check_registration'
        else:
            status = 'check_in_licensed_editor'
        rows.append({'id':ident, 'name':name, 'operation':scope, 'status':status,
                     'com_registration_for_this_python':classes, 'runtime_verified':False})
    return {'platform':system, 'machine':platform.machine(), 'products':rows}
