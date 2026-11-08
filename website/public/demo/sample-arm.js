// Invented desktop arm, in illustrative millimetres. Not a manufacturing model.
const add=(a,b)=>a.map((v,i)=>v+b[i]);
const sub=(a,b)=>a.map((v,i)=>v-b[i]);
const mul=(a,k)=>a.map(v=>v*k);
const cross=(a,b)=>[a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]];
const unit=a=>mul(a,1/Math.hypot(...a));
function basis(a,b){const w=unit(sub(b,a)),u=unit(cross(w,Math.abs(w[2])<.9?[0,0,1]:[0,1,0]));return [u,cross(w,u)];}
function cylinder(a,b,r,segments=32){
 const [u,v]=basis(a,b),ring=c=>Array.from({length:segments},(_,i)=>add(c,add(mul(u,r*Math.cos(i*2*Math.PI/segments)),mul(v,r*Math.sin(i*2*Math.PI/segments))))),lo=ring(a),hi=ring(b),t=[];
 for(let i=0;i<segments;i++){const j=(i+1)%segments;t.push([a,lo[j],lo[i]],[b,hi[i],hi[j]],[lo[i],lo[j],hi[j]],[lo[i],hi[j],hi[i]]);}return t;
}
function beam(a,b,width,depth,endWidth=width){
 const [u,v]=basis(a,b),ring=(p,w)=>[[-1,-1],[1,-1],[1,1],[-1,1]].map(([x,y])=>add(p,add(mul(u,x*w/2),mul(v,y*depth/2)))),p=[...ring(a,width),...ring(b,endWidth)];
 return [[0,2,1],[0,3,2],[4,5,6],[4,6,7],[0,1,5],[0,5,4],[1,2,6],[1,6,5],[2,3,7],[2,7,6],[3,0,4],[3,4,7]].map(f=>f.map(i=>p[i]));
}
const joint=(p,r,width)=>cylinder(add(p,[0,-width/2,0]),add(p,[0,width/2,0]),r);
const stl=triangles=>'solid desktop_arm\n'+triangles.map(t=>'facet normal 0 0 0\nouter loop\n'+t.map(v=>'vertex '+v.map(n=>Number(n.toFixed(5))).join(' ')+'\n').join('')+'endloop\nendfacet\n').join('')+'endsolid desktop_arm\n';
const shoulder=[0,0,52],elbow=[24,0,133],wrist=[-57,0,162];
export const armBase=()=>stl([...cylinder([0,0,0],[0,0,9],38),...cylinder([0,0,9],[0,0,25],29),...beam([0,0,25],shoulder,27,32),...joint(shoulder,19,40)]);
export const armLinks=()=>stl([...beam(shoulder,elbow,25,24,20),...joint(elbow,17,34),...beam(elbow,wrist,21,22,17),...joint(wrist,13,32)]);
export const armGripper=()=>stl([...beam(wrist,[-77,0,168],16,18),...beam([-78,-14,168],[-78,14,168],9,10),...beam([-79,-14,168],[-103,-14,176],7,9),...beam([-103,-14,176],[-113,-8,179],6,9),...beam([-79,14,168],[-103,14,176],7,9),...beam([-103,14,176],[-113,8,179],6,9)]);
export const armBracket=offset=>stl([...beam([-49,14,153],[-49,offset,153],4,11),...beam([-49,offset,153],[-49,offset,175],4,11)]);
