// Read-only activity monitoring. The user decides when to apply new information.
const signature=value=>value.activity_token||JSON.stringify({...value,seq:undefined});
export function createActivityMonitor({api,notice}){
  let source=null,generation=0,pending=false;
  function clear(){generation++;source=null;notice('');}
  function set(command,args,value){clear();source={command,args,signature:signature(value)};}
  async function check(){
    if(!source||pending)return;
    const epoch=generation,current=source;pending=true;
    try{
      const value=await api(current.command,current.args);
      if(epoch===generation)notice(signature(value)!==current.signature?'New activity is available. Your view has not changed.':'');
    }catch{
      if(epoch===generation)notice('Live updates unavailable. Load updates to retry.');
    }finally{pending=false;}
  }
  return {set,clear,check};
}
