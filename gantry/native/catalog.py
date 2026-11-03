"""Exact operation coverage, never a claim of full product integration."""
PRODUCTS = {
    'solidworks': ('SOLIDWORKS', 'direct', 'part dimension in active configuration'),
    'catia-v5': ('CATIA V5', 'direct', 'existing numeric part parameter'),
    'creo': ('Creo Parametric', 'direct', 'existing scalar model parameter'),
    'solidworks-electrical': ('SOLIDWORKS Electrical', 'direct', 'existing project user-data field'),
    'altium': ('Altium Designer', 'script', 'existing PCB component comment'),
    'cadence': ('Cadence Allegro PCB Editor', 'script', 'existing design string property'),
    'zuken-e3': ('Zuken E3.series', 'sdk_required', 'version-specific read/write and persistence SDK signatures required'),
    'capital': ('Siemens Capital', 'sdk_required', 'module/version-specific licensed SDK required'),
}


def catalog():
    return [{'id':ident,'name':name,'route':route,'scope':scope,
             'native_runtime_verified':False,'physical_validation':False,
             'dispatch_route':('explicit_pinned_executable' if ident=='altium' else
                'manual_host_script' if route=='script' else 'attach_existing' if route=='direct' else 'not_implemented'),
             'persistence_route':('opt_in_save_reload_capture' if ident=='altium' else
                'native_update_readback' if route=='direct' else 'not_implemented'),
             'status':'blocked_sdk' if route=='sdk_required' else 'experimental_contract_tested'}
            for ident,(name,route,scope) in PRODUCTS.items()]
