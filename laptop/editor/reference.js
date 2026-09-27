// Sensor-native pixels; camera-local +Y is up, viewing direction is -Z.
export function photoProjection(element, reference) {
  if(!element.spatial || !reference)return null;
  const m=reference.camera_to_world_column_major,k=reference.intrinsics_column_major;
  const world=element.spatial.transform.slice(12,15),delta=world.map((x,i)=>x-m[12+i]);
  const p=[0,1,2].map(c=>delta.reduce((sum,x,r)=>sum+m[c*4+r]*x,0));
  if(p[2]>=-.02)return null;
  const u=(k[0]*p[0]/-p[2]+k[6])/reference.image_width;
  const v=(k[4]*-p[1]/-p[2]+k[7])/reference.image_height;
  return u>=0 && u<=1 && v>=0 && v<=1 ? [u,v] : null;
}
