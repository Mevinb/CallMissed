import {readFileSync} from 'node:fs';
import {runInNewContext} from 'node:vm';
import {test} from 'node:test';
import assert from 'node:assert/strict';
const code=readFileSync(new URL('../public/pcm-capture.js',import.meta.url),'utf8');
for(const rate of [24000,44100,48000]){
  test(`encodes ${rate} Hz microphone audio into 24kHz mono PCM16`,()=>{
    const frames=[];let Capture;
    runInNewContext(code,{AudioWorkletProcessor:class{constructor(){this.port={postMessage:bytes=>frames.push(bytes)};}},sampleRate:rate,registerProcessor:(_name,implementation)=>Capture=implementation});
    const capture=new Capture();
    for(let position=0;position<rate+2;position+=128){const input=new Float32Array(Math.min(128,rate+2-position)).fill(0.5);assert.equal(capture.process([[input]]),true);}
    assert.equal(frames.length,50);assert.equal(frames[0].byteLength,960);assert.equal(new DataView(frames[1]).getInt16(0,true),16384);
  });
}
test('clips floating audio values to signed PCM16',()=>{
 let Capture;const frames=[];runInNewContext(code,{AudioWorkletProcessor:class{constructor(){this.port={postMessage:bytes=>frames.push(bytes)};}},sampleRate:24000,registerProcessor:(_name,implementation)=>Capture=implementation});const capture=new Capture();capture.process([[new Float32Array(481).fill(-2)]]);assert.equal(new DataView(frames[0]).getInt16(0,true),-32768);
});
