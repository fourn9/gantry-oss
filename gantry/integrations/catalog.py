"""Public capability inventory, not an assertion of vendor certification."""
SOURCE = 'https://www.flowengineering.com/integrations'
REVIEWED = '2026-11-02'
CURRENT = {
    'confluence':'Confluence', 'cursor':'Cursor', 'excel':'Excel', 'github':'GitHub',
    'gitlab':'GitLab', 'google-drive':'Google Drive', 'google-sheets':'Google Sheets',
    'jira':'Jira', 'linear':'Linear', 'notion':'Notion', 'onshape':'Onshape',
    'python':'Python', 'relyence':'Relyence', 'sharepoint':'SharePoint', 'slack':'Slack'}
COMING = {
    'altium-365':'Altium 365', 'ansys':'Ansys', 'duro':'Duro', 'epsilon3':'Epsilon 3',
    'exotrail':'Exotrail', 'ion':'First Resonance ION', 'fusion360':'Fusion 360',
    'fusion-stoke':'Fusion by Stoke', 'manufacturo':'Manufacturo', 'matlab':'Matlab',
    'teams':'Microsoft Teams', 'simscale':'SimScale', 'nx':'Siemens NX', 'solidworks':'SolidWorks'}
HOME_ONLY = {'dassault':'Dassault (product unspecified)', 'outlook':'Outlook',
             'abaqus':'Abaqus', 'labview':'LabVIEW', 'teststand':'TestStand', 'dspace':'dSPACE'}
API = {'confluence','excel','github','gitlab','google-drive','google-sheets','jira',
       'linear','notion','onshape','sharepoint','slack'}


ROBOTICS = {
    'onnx': ('ONNX', 'saved_model_interface', 'https://onnx.ai/onnx/api/serialization.html',
             'Saved model and declared tensor interface. External weights, training and inference are separate.'),
    'mujoco': ('MuJoCo', 'existing_runtime_checkpoint', 'https://mujoco.readthedocs.io/',
               'Python checkpoint API plus operator-selected saved files; no live simulator subscription.'),
    'freecad': ('FreeCAD', 'mac_step_import_and_reopen', 'https://www.freecad.org/',
                'Selected STEP imported as a static shape in macOS FreeCAD. Native vendor constraints are unavailable.'),
    'kicad': ('KiCad', 'local_erc_drc', 'https://docs.kicad.org/10.0/en/cli/cli.html',
              'Operator-local checks on selected saved designs; missing project dependencies can affect results.'),
    'mcap': ('MCAP (ROS 2 / Foxglove)', 'recording_index', 'https://mcap.dev/spec',
             'Selected saved MCAP and recorder index only. Live ROS subscriptions and cloud accounts are separate.'),
}


def catalog():
    from .write_recipes import OPERATIONS, ATOMIC
    rows=[]
    for group,names in [('listed',CURRENT),('coming_soon',COMING),('home_logo_only',HOME_ONLY)]:
        for ident,name in names.items():
            routes=['saved_export']
            if ident in API: routes.append('scoped_api_read')
            if ident in OPERATIONS: routes.append('planned_native_update')
            if ident=='excel': routes.append('local_xlsx_cells')
            if ident=='cursor': routes.append('existing_project_mcp')
            if ident=='python': routes.append('existing_scoped_runner')
            if ident in {'notion','slack'}: routes.append('bounded_related_capture')
            if ident in {'google-drive','sharepoint'}: routes.append('revision_checked_file_download')
            rows.append({'id':ident,'name':name,'reference_status':group,'routes':routes,
                'native_write':ident in OPERATIONS,'native_write_operations':sorted(OPERATIONS.get(ident,[])),
                'write_concurrency':{op:('provider_condition' if (ident,op) in ATOMIC else 'preflight_only')
                                     for op in sorted(OPERATIONS.get(ident,[]))},'live_account_verified':False,
                'limitation':('Selected read/update API contracts tested; live credentials not tested; see operation scope.' if ident in API else
                    'Saved export capture is not native synchronization or native editing.'),
                'source':SOURCE if group!='home_logo_only' else 'https://www.flowengineering.com/',
                'reviewed_at':REVIEWED})
    for ident, (name, route, source, limitation) in ROBOTICS.items():
        rows.append({'id': ident, 'name': name, 'reference_status': 'robotics',
                     'routes': ['saved_export', route], 'source': source, 'reviewed_at': '2026-11-24',
                     'native_write': False, 'native_write_operations': [], 'write_concurrency': {},
                     'live_account_verified': False, 'limitation': limitation})
    return rows


def known(provider):
    from ..native.catalog import PRODUCTS
    return provider in CURRENT or provider in COMING or provider in HOME_ONLY or provider in PRODUCTS or provider in ROBOTICS
