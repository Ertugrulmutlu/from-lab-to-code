import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

const PALETTE = {red: 0xfa6770, green: 0x52d8a9, blue: 0x66a8ff};
const V = (x, y, z) => new THREE.Vector3(x, z, y); // model z-up -> Three y-up
const material = (color, metalness = 0.1, roughness = 0.54) => new THREE.MeshStandardMaterial({color, metalness, roughness});

export class RobotView {
  constructor(container) {
    this.container = container;
    this.scene = new THREE.Scene();
    this.scene.background = new THREE.Color('#0a1725');
    this.scene.fog = new THREE.FogExp2(0x0a1725, 0.025);
    this.camera = new THREE.PerspectiveCamera(42, 1, 0.1, 100);
    this.camera.position.set(4.7, 4.7, 6.9);
    this.camera.lookAt(0, 0.8, 0);
    this.renderer = new THREE.WebGLRenderer({antialias: true, alpha: false});
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    this.renderer.shadowMap.enabled = true;
    this.renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    this.renderer.outputColorSpace = THREE.SRGBColorSpace;
    container.appendChild(this.renderer.domElement);
    this.controls = new OrbitControls(this.camera, this.renderer.domElement);
    this.controls.target.set(0, 0.8, 0);
    this.controls.enableDamping = true;
    this.controls.minDistance = 3.7;
    this.controls.maxDistance = 13;
    this.controls.maxPolarAngle = Math.PI / 2.05;
    this.controls.update();
    this.scene.add(new THREE.HemisphereLight(0xc4e8ff, 0x142638, 2.7));
    const sun = new THREE.DirectionalLight(0xe1f0ff, 3.5);
    sun.position.set(-3, 7, 5); sun.castShadow = true;
    sun.shadow.mapSize.set(2048, 2048);
    sun.shadow.camera.left = -7;sun.shadow.camera.right = 7;sun.shadow.camera.top = 7;sun.shadow.camera.bottom = -7;
    this.scene.add(sun);
    this._buildCell();
    this.resizeObserver = new ResizeObserver(() => this.resize());
    this.resizeObserver.observe(container);
    this.resize();
    this.animate();
  }
  box(parent, size, pos, color, options = {}) {
    const m = new THREE.Mesh(new THREE.BoxGeometry(...size), material(color, options.metalness ?? 0.13, options.roughness ?? 0.5));
    m.position.set(...pos); m.castShadow = true; m.receiveShadow = true; parent.add(m);return m;
  }
  cylinder(parent, radiusTop, radiusBottom, length, color, pos, rotation = [0, 0, 0]) {
    const m = new THREE.Mesh(new THREE.CylinderGeometry(radiusTop, radiusBottom, length, 20), material(color, 0.35));
    m.position.set(...pos);m.rotation.set(...rotation);m.castShadow=true;m.receiveShadow=true;parent.add(m);return m;
  }
  _buildCell() {
    const grid = new THREE.GridHelper(12, 24, 0x274257, 0x1a3245);
    grid.material.transparent = true;grid.material.opacity=.40;this.scene.add(grid);
    const floor = new THREE.Mesh(new THREE.PlaneGeometry(200,200),material(0x102033,0,.9));
    floor.rotation.x = -Math.PI/2;floor.position.y=-.035;floor.receiveShadow=true;this.scene.add(floor);
    const deck = material(0x17334a,0.5,.5);
    const belt = this.box(this.scene,[4.1,.13,.53],[-.76,.58,1.05],0x244961,{metalness:.4});
    this.box(this.scene,[4.04,.035,.40],[-.76,.66,1.05],0x2c8897,{metalness:.3,roughness:.8});
    for (const z of [.72,1.38]) this.box(this.scene,[4.12,.12,.055],[-.76,.72,z],0x778ca5,{metalness:.75});
    for (const x of [-2.65,.98]) for (const z of [.79,1.31]) this.box(this.scene,[.13,.57,.13],[x,.28,z],0x506781,{metalness:.65});
    for (let i=0;i<12;i++) this.box(this.scene,[.03,.003,.4],[-2.65+i*.34,.684,1.05],0x4da5a5);
    this.cylinder(this.scene,.16,.20,.15,0x5c7e94,[0,.08,-.45]);
    this.cylinder(this.scene,.25,.26,.24,0x9bb3c3,[0,.25,-.45]);
    this.cylinder(this.scene,.13,.16,.51,0x6b8aa3,[0,.58,-.45]);
    this.cylinder(this.scene,.19,.19,.17,0x2a3f57,[0,.85,-.45]);
    this.upper = this.segment(0x91aabf,.14);
    this.lower = this.segment(0x6b90a8,.115);
    this.elbowJoint=this.cylinder(this.scene,.17,.17,.25,0x233f57,[0,0,0]);
    this.wristJoint=this.cylinder(this.scene,.14,.14,.20,0x244d67,[0,0,0]);
    this.grip = this.cylinder(this.scene,.055,.095,.22,0x101d30,[0,0,0]);
    this.gripSignal=new THREE.PointLight(0x66f0cc,0,1.0);
    this.scene.add(this.gripSignal);
    this.pickMarker = new THREE.Mesh(new THREE.TorusGeometry(.20,.025,8,36),new THREE.MeshBasicMaterial({color:0x6be4d8}));
    this.pickMarker.rotation.x=-Math.PI/2;this.pickMarker.position.set(.72,.73,1.05);this.scene.add(this.pickMarker);
    this.sensorBeam=this.box(this.scene,[.025,.35,.025],[.72,.96,1.05],0x4ec7c2);
    this.sensorBeam.material.transparent=true;this.sensorBeam.material.opacity=.25;
    this.binCubes={};
    Object.entries({red:[-1.34,-1.75],green:[0,-1.86],blue:[1.34,-1.75]}).forEach(([color,[x,y]])=>{
      this.box(this.scene,[.72,.10,.77],[x,.38,y],PALETTE[color]);
      this.box(this.scene,[.72,.10,.77],[x,.15,y],0x334e66);
      this.box(this.scene,[.72,.33,.065],[x,.56,y+.36],0x334e66);
      this.box(this.scene,[.72,.33,.065],[x,.56,y-.36],0x334e66);
      this.box(this.scene,[.065,.33,.72],[x-.34,.56,y],0x334e66);
      this.box(this.scene,[.065,.33,.72],[x+.34,.56,y],0x334e66);
      this.binCubes[color]=[];
    });
    this.item = this.box(this.scene,[.28,.28,.28],[-2.2,.78,1.05],PALETTE.blue);
    this.item.visible=false;
  }
  segment(color,radius){
    const mesh = new THREE.Mesh(new THREE.CylinderGeometry(radius,radius,1,18),material(color,.56,.3));
    mesh.castShadow=true;mesh.receiveShadow=true;this.scene.add(mesh);return mesh;
  }
  align(mesh,start,end){
    const a=V(...start),b=V(...end),d=b.clone().sub(a);
    mesh.position.copy(a.add(b).multiplyScalar(.5));
    mesh.quaternion.setFromUnitVectors(new THREE.Vector3(0,1,0),d.clone().normalize());
    mesh.scale.set(1,d.length(),1);
  }
  update(state){
    const j=state.robot.joints;
    this.align(this.upper,j.shoulder,j.elbow);
    this.align(this.lower,j.elbow,j.wrist);
    this.elbowJoint.position.copy(V(...j.elbow));
    this.wristJoint.position.copy(V(...j.wrist));
    this.grip.position.copy(V(j.wrist[0],j.wrist[1],j.wrist[2]+.10));
    this.gripSignal.position.copy(V(...j.wrist));
    this.gripSignal.intensity=state.robot.gripping?1.6:0;
    this.item.visible=Boolean(state.box);
    if(state.box){
      const {x,y,z,color}=state.box;
      this.item.position.copy(V(x,y,z));
      this.item.material.color.setHex(PALETTE[color]||PALETTE.blue);
    }
    this.sensorBeam.material.opacity=state.detected_color?.85:.25;
    for(const color of Object.keys(this.binCubes)){
      // Display actual item colors in each target bin, including mis-sorts.
      const contents = state.bin_contents?.[color] || {[color]:state.counts[color]};
      const items = Object.entries(contents).flatMap(([actual,n])=>Array(Math.min(n,5)).fill(actual)).slice(0,5);
      const list = this.binCubes[color];
      while(list.length<items.length){
        const center={red:[-1.34,-1.75],green:[0,-1.86],blue:[1.34,-1.75]}[color];
        const index=list.length;
        const x=center[0]+((index%2)-.5)*.24;
        const z=center[1]+((Math.floor(index/2)%2)-.5)*.24;
        const cube=this.box(this.scene,[.19,.19,.19],[x,.52+Math.floor(index/4)*.19,z],PALETTE[items[index]]);
        list.push(cube);
      }
      list.forEach((cube,index)=>cube.material.color.setHex(PALETTE[items[index]]));
      while(list.length>items.length){const cube=list.pop();this.scene.remove(cube);cube.geometry.dispose();cube.material.dispose();}
    }
  }
  resetCamera(){this.camera.position.set(4.7,4.7,6.9);this.controls.target.set(0,.8,0);this.controls.update();}
  resize(){const w=Math.max(1,this.container.clientWidth),h=Math.max(1,this.container.clientHeight);this.camera.aspect=w/h;this.camera.updateProjectionMatrix();this.renderer.setSize(w,h,false);}
  animate(){requestAnimationFrame(()=>this.animate());this.controls.update();this.renderer.render(this.scene,this.camera);}
}
