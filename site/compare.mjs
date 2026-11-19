import {normNote} from "./frames.mjs";
import {readMessage, compareAttitudes} from "./messages.mjs";
import {attitudeScene} from "./scene.mjs";

const $=id=>document.getElementById(id);
const identity = "q: [1, 0, 0, 0]";
const north = "orientation: {x: 0, y: 0, z: 0.7071067811865476, w: 0.7071067811865476}";
const examples={
  roll: [identity,"orientation: {x: 0.5, y: 0.5, z: 0.5, w: 0.5}"],
  match: [identity,north],
  opposite: [identity,"orientation: {x: 0, y: 0, z: -0.7071067811865476, w: -0.7071067811865476}"],
  time:["timestamp_sample: 1000000\n"+identity, "header:\n  stamp: {sec: 1, nanosec: 20000000}\n"+north]
};
const expectedView=attitudeScene($("expected"),(az,el)=>observedView.camera(az,el));
const observedView=attitudeScene($("actual"),(az,el)=>expectedView.camera(az,el));
$("reset-camera").onclick=()=>{expectedView.reset();observedView.reset();};
for(const [id,view] of [["expected",expectedView],["actual",observedView]]) {
  $(id).onkeydown=e=>{
    const delta={ArrowLeft:[-.13,0],ArrowRight:[.13,0],ArrowUp:[0,.12],ArrowDown:[0,-.12]}[e.key];
    if(delta){e.preventDefault();view.orbit(...delta);}
  };
}
let current;
function summaryText(node,text){
  const p=document.createElement("p");p.textContent=text;node.append(p);
}
function formatQ(q){return "["+q.map(v=>Number(v.toFixed(6))).join(", ")+"]";}
function degrees(value){return value>0 && value<.005 ? "< 0.005°" : value.toFixed(2)+"°";}
function labeledInput(system){
  try{return readMessage($(system).value,system);}
  catch(e){throw Error((system==="ros"?"ROS":"PX4")+" input · "+e.message);}
}
function invalidate(message){
  current=null;$("result").hidden=true;$("feedback").textContent=message;
}
function compare(){
  try{
    const px4=labeledInput("px4"),ros=labeledInput("ros");
    const result=compareAttitudes(px4,ros,$("shared").checked);
    current={px4,ros,result};$("result").hidden=false;$("feedback").textContent="";
    $("angle").value=degrees(result.rotationDeg);$("nose").value=degrees(result.forwardDeg);
    $("offset").value=result.timeOffsetMs===null?"Unavailable":Number(result.timeOffsetMs.toPrecision(8))+" ms";
    expectedView.pose(px4.q);observedView.pose(result.observedPx4);
    $("expected-q").textContent=formatQ(result.expected);$("actual-q").textContent=formatQ(result.observed);
    const details=$("diagnostics");details.replaceChildren();
    summaryText(details,"PX4 · "+normNote(px4.raw));
    summaryText(details,"ROS · "+normNote(ros.raw));
    if(ros.world || ros.child)summaryText(details,"ROS header.frame_id: "+(ros.world||"unspecified")+" · child_frame_id: "+(ros.child||"unspecified")+". Verify geographic and body-axis alignment in your TF tree.");
    const stamps=[["PX4",px4],["ROS",ros]].map(([name,m])=>name+" "+(m.stampNs===null?"stamp unavailable":m.stampField+" = "+m.stampNs+" ns"));
    summaryText(details,stamps.join(" · "));
    if(px4.stampNs!==null && ros.stampNs!==null && !$("shared").checked)
      summaryText(details,"Time offset requires a shared clock and epoch.");
  }catch(e){invalidate(e.message);}
}
function setExample(name){
  $("example").value=name;
  [$("px4").value,$("ros").value]=examples[name];
  $("shared").checked=name==="time"; compare();
}
$("example").onchange=()=>setExample($("example").value);
$("pair-form").onsubmit=e=>{e.preventDefault();compare();};
for (const id of ["px4","ros"])$(id).oninput=()=>{
  $("example").value="custom";invalidate("Inputs changed. Compare attitudes to update the result.");
};
$("shared").onchange=()=>{if(current)compare();};
setExample("roll");
