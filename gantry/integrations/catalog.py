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
            rows.append({'id':ident,'name':name,'reference_status':group,'routes':routes,
                'native_write':ident in OPERATIONS,'native_write_operations':sorted(OPERATIONS.get(ident,[])),
                'write_concurrency':{op:('provider_condition' if (ident,op) in ATOMIC else 'preflight_only')
                                     for op in sorted(OPERATIONS.get(ident,[]))},'live_account_verified':False,
                'limitation':('Selected read/update API contracts tested; live credentials not tested; see operation scope.' if ident in API else
                    'Saved export capture is not native synchronization or native editing.'),
                'source':SOURCE if group!='home_logo_only' else 'https://www.flowengineering.com/',
                'reviewed_at':REVIEWED})
    return rows


def known(provider):
    return provider in CURRENT or provider in COMING or provider in HOME_ONLY
