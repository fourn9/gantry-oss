// randomUUID is only exposed in secure contexts by some mobile browsers. The
// pilot can be opened over a private LAN HTTP address, so keep idempotency
// keys working there as well.
export const intentKey=()=>{
  if(globalThis.crypto?.randomUUID)return globalThis.crypto.randomUUID();
  if(globalThis.crypto?.getRandomValues){
    const bytes=new Uint8Array(16);globalThis.crypto.getRandomValues(bytes);
    bytes[6]=(bytes[6]&15)|64;bytes[8]=(bytes[8]&63)|128;
    const hex=[...bytes].map(value=>value.toString(16).padStart(2,'0')).join('');
    return `${hex.slice(0,8)}-${hex.slice(8,12)}-${hex.slice(12,16)}-${hex.slice(16,20)}-${hex.slice(20)}`;
  }
  return 'fallback-'+Date.now().toString(36)+'-'+Math.random().toString(36).slice(2);
};
