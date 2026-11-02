"""Fixed native calls, not arbitrary COM dispatch. Sources: docs/NATIVE-DESKTOP.md."""
from pathlib import Path
from ..model import require, Fault


class SolidWorks:
    def __init__(self, app, save_document): self.app,self.save_document=app,save_document
    def inspect(self, config):
        doc=self.app.ActiveDoc
        require(doc is not None and doc.GetType()==1,'unsupported','Only an active saved part is supported')
        parameter=doc.Parameter(config['selector'])
        require(parameter is not None,'not_found','Dimension not found')
        values=parameter.GetSystemValue3(1,None)  # swThisConfiguration; SI metres/radians
        require(len(values)==1,'unsupported','Expected one configuration value')
        return {'document':str(doc.GetPathName()),'dirty':bool(doc.GetSaveFlag()),
                'application_version':str(self.app.RevisionNumber()),
                'configuration':str(doc.ConfigurationManager.ActiveConfiguration.Name),
                'value':float(values[0]),'unit':'SI'}, [str(doc.GetPathName())]
    def write(self, config, value):
        doc=self.app.ActiveDoc
        require(doc.Parameter(config['selector']).SetSystemValue3(value,1,None)==0,
                'native_write_failed','SOLIDWORKS rejected dimension update')
        require(doc.EditRebuild3(),'native_rebuild_failed','SOLIDWORKS rebuild failed; document may be modified')
        return self.save_document(doc)


class Catia:
    def __init__(self, app): self.app=app
    def inspect(self, config):
        doc=self.app.ActiveDocument; parameter=doc.Part.Parameters.Item(config['selector'])
        require(not parameter.ReadOnly,'scope_denied','Parameter is read-only')
        # A driven parameter must be changed through its relation, not overwritten.
        require(parameter.OptionalRelation is None,'unsupported','Relation-driven parameter is not supported')
        require(type(parameter.Value) in (int,float),'unsupported','Numeric part parameter required')
        cfg=self.app.SystemConfiguration
        return {'document':str(doc.FullName),'dirty':not bool(doc.Saved),
                'application_version':f'{cfg.Version}.{cfg.Release}.{cfg.ServicePack}',
                'value':parameter.Value,'unit':'native'}, [str(doc.FullName)]
    def write(self, config, value):
        doc=self.app.ActiveDocument; doc.Part.Parameters.Item(config['selector']).Value=value
        doc.Part.Update(); doc.Save()
        require(doc.Saved,'native_save_failed','CATIA did not report a saved document')
        return {'saved':True}


class Creo:
    def __init__(self, connection, factory): self.connection,self.factory=connection,factory
    def inspect(self, config):
        session=self.connection.Session; model=session.CurrentModel
        require(model is not None and str(model.FileName).lower().endswith('.prt'),
                'unsupported','Only a local native part is supported')
        origin=Path(str(model.Origin))
        # Origin is the directory; no Windchill URL or unrelated working directory.
        require(origin.is_absolute() and origin.is_dir(),'unsupported','Local model origin required')
        require(Path(str(session.GetCurrentDirectory())).resolve()==origin.resolve(),
                'scope_denied','Creo save directory must equal model origin')
        parameter=model.GetParam(config['selector'])
        require(parameter is not None,'not_found','Model parameter not found')
        field={'double':'DoubleValue','integer':'IntValue','string':'StringValue','boolean':'BoolValue'}[config['value_type']]
        value=getattr(parameter.Value,field)  # PTC union raises on mismatched type.
        filename=str(model.FileName)
        candidates=[]
        for path in origin.iterdir():
            suffix=path.name[len(filename)+1:] if path.name.startswith(filename+'.') else ''
            if path.name==filename or suffix.isdigit(): candidates.append((int(suffix or 0),path))
        require(candidates,'not_found','Saved Creo part file not found')
        latest=max(candidates,key=lambda item:item[0])[1]
        return {'document':str(origin/filename),'dirty':bool(model.IsModified),
                'application_version':None,'version_capture':'not_available_in_async_driver',
                'model_version_stamp':str(model.VersionStamp),'value':value,'unit':'native'}, [str(latest)]
    def write(self, config, value):
        model=self.connection.Session.CurrentModel
        if config['value_type']=='double': native=self.factory.CreateDoubleParamValue(value)
        elif config['value_type']=='integer': native=self.factory.CreateIntParamValue(value)
        elif config['value_type']=='boolean': native=self.factory.CreateBoolParamValue(value)
        else: native=self.factory.CreateStringParamValue(value)
        model.GetParam(config['selector']).Value=native
        model.Regenerate(None); model.Save()
        require(not model.IsModified,'native_save_failed','Creo still reports modified state')
        return {'saved':True,'versioned_save':True}


class Electrical:
    """comtypes binding: explicit out error code followed by retval, per vendor Python sample."""
    def __init__(self, app, no_error): self.app,self.no_error=app,no_error
    def result(self, result):
        require(isinstance(result,(tuple,list)) and len(result)==2 and result[0]==self.no_error,
                'native_api_failed','Electrical API returned an error or unsupported binding')
        return result[1]
    def project(self, config):
        project=self.result(self.app.getEwProjectCurrent())
        require(project is not None and str(project.getID())==config['project_id'],
                'scope_denied','Active Electrical project ID differs')
        return project
    def inspect(self, config):
        project=self.project(config)
        env=self.result(self.app.getEwEnvironment())
        environment={'hostname':str(self.result(env.getHostname())),
                     'working_folder':str(self.result(env.getWorkingFolder()))}
        require(environment==config['environment'],'scope_denied','Electrical environment differs')
        return {'document':config['project_id'],'environment':environment,'dirty':None,
                'dirty_capture':'unrelated_editor_state_not_captured',
                'application_version':str(self.app.getApplicationVersion()),
                'modification_date':str(self.result(project.getModificationDate())),
                'value':str(self.result(project.getUserData(config['field']))),'unit':'text',
                'native_file_capture':'not_captured_database_backed_project'}, []
    def write(self, config, value):
        project=self.project(config)
        require(project.setUserData(config['field'],value)==self.no_error,
                'native_write_failed','Electrical user-data update failed')
        require(project.update()==self.no_error,'native_save_failed','Electrical project update failed')
        return {'database_update':True}


def connect(product, credential_ref=None):
    """Attach only. Never launches/opens a document or accepts a caller-selected ProgID."""
    import sys
    require(sys.platform=='win32','platform_unavailable','Licensed Windows application required')
    try:
        if product=='solidworks-electrical':
            import comtypes.client
            from ..github_connector import credential
            factory=comtypes.client.GetActiveObject('EwAPI.EwInteropFactoryX')
            # Import generated vendor constants only after COM type information is loaded.
            from comtypes.gen.EwAPI import EW_NO_ERROR
            helper=Electrical(None,EW_NO_ERROR)
            app=helper.result(factory.getEwApplication(credential(credential_ref)))
            return Electrical(app,EW_NO_ERROR)
        import win32com.client
        if product=='solidworks':
            import pythoncom
            def save_document(doc):
                errors=win32com.client.VARIANT(pythoncom.VT_BYREF|pythoncom.VT_I4,0)
                warnings=win32com.client.VARIANT(pythoncom.VT_BYREF|pythoncom.VT_I4,0)
                ok=doc.Save3(1,errors,warnings)  # silent; no SaveReferenced option
                require(ok and errors.value==0,'native_save_failed','SOLIDWORKS save failed')
                return {'errors':errors.value,'warnings':warnings.value}
            return SolidWorks(win32com.client.GetActiveObject('SldWorks.Application'),save_document)
        if product=='catia-v5': return Catia(win32com.client.GetActiveObject('CATIA.Application'))
        if product=='creo':
            factory=win32com.client.Dispatch('pfcls.CCpfcAsyncConnection')
            connection=factory.Connect('','','',10)
            return Creo(connection,win32com.client.Dispatch('pfcls.CMpfcModelItem'))
    except ImportError:
        raise Fault('dependency_missing','Install the documented Windows COM dependency') from None
    except Fault: raise
    except Exception:
        raise Fault('vendor_unavailable','Check installed SDK, license, active application and type library') from None
    raise Fault('unsupported','Use the product-specific script route or supply the missing SDK')
