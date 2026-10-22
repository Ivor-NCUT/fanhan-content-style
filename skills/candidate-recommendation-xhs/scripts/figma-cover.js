// Run through use_figma after replacing __POST_JSON__ with the approved post JSON.
// Create native TEXT nodes; never import SVG text as a substitute for editable text.
const post = __POST_JSON__;
if (!Array.isArray(post.lines) || post.lines.length !== 4 || post.lines.some(s => typeof s !== 'string' || !s || s.includes('\n'))) throw new Error('Expected four headline lines');
const available = await figma.listAvailableFontsAsync();
const font = available.map(x => x.fontName).find(f => f.family === 'Alibaba PuHuiTi 3.0' && /bold/i.test(f.style))
  || available.map(x => x.fontName).find(f => f.family === 'PingFang SC' && /semibold|medium/i.test(f.style))
  || available.map(x => x.fontName).find(f => f.family === 'Noto Sans SC' && /bold/i.test(f.style));
if (!font) throw new Error('No approved Chinese font found; inspect available fonts before choosing an alternative');
await figma.loadFontAsync(font);
const createdNodeIds = [];
const rgb = hex => ({r:parseInt(hex.slice(0,2),16)/255,g:parseInt(hex.slice(2,4),16)/255,b:parseInt(hex.slice(4,6),16)/255});
const paint = hex => [{type:'SOLID',color:rgb(hex)}];
let right = 0;
for (const n of figma.currentPage.children) right = Math.max(right,n.x+n.width);
const frame = figma.createFrame(); createdNodeIds.push(frame.id);
frame.name = '候选人推荐封面 · 原生可编辑文字'; frame.resize(1200,1600); frame.x=right+100; frame.y=0;frame.fills=paint('fffefa');
function rect(name,x,y,w,h,fill) {const n=figma.createRectangle();createdNodeIds.push(n.id);frame.appendChild(n);n.name=name;n.x=x;n.y=y;n.resize(w,h);n.fills=paint(fill);return n;}
function text(name,s,x,y,size) {const n=figma.createText();createdNodeIds.push(n.id);frame.appendChild(n);n.name=name;n.fontName=font;n.fontSize=size;n.lineHeight={unit:'PIXELS',value:size*1.2};n.characters=s;n.textAutoResize='WIDTH_AND_HEIGHT';n.x=x;n.y=y;n.fills=paint('504d48');return n;}
try {
 const quote=figma.createNodeFromSvg('<svg xmlns="http://www.w3.org/2000/svg" width="133" height="104" viewBox="144 124 133 104"><path d="M144 228v-45q0-49 53-59l4 23q-28 6-29 28h29v53zm76 0v-45q0-49 53-59l4 23q-28 6-29 28h29v53z" fill="#f3ecdc"/></svg>');
 frame.appendChild(quote);quote.name='装饰引号';quote.x=144;quote.y=124;createdNodeIds.push(quote.id,...quote.findAll().map(n=>n.id));
 for (let i=0;i<4;i++) {
  const highlight=(i===0||i===3)?rect('绿色标记-'+i,65,430+i*230-42,1,56,'b0ff67'):null;
  const n=text('主文案-'+(i+1),post.lines[i],65,280+i*230,150);
  if (n.width>1060) throw new Error('Headline overflows; shorten content rather than shrinking type');
  if(highlight) highlight.resize(n.width+12,56);
 }
 const subtitle=text('求职偏好',post.subtitle||'',70,1266,34);
 if(subtitle.width>1060)throw new Error('Subtitle overflows');
 rect('底部装饰',976,1435,80,19,'f3ecdc');
 const texts=frame.findAllWithCriteria({types:['TEXT']});
 if(texts.length!==5)throw new Error('Expected 5 native TEXT nodes');
 // A reversible edit proves that characters can be changed without rebuilding vectors.
 const before=texts[0].characters; texts[0].characters=before+'验';
 if(texts[0].characters!==before+'验')throw new Error('Text editing failed');
 texts[0].characters=before;
 figma.currentPage.selection=[frame];figma.viewport.scrollAndZoomIntoView([frame]);
 return {createdNodeIds,frameId:frame.id,font,editRoundTrip:true,textNodes:texts.map(n=>({id:n.id,type:n.type,name:n.name,characters:n.characters,fontName:n.fontName,width:n.width,height:n.height,x:n.x,y:n.y}))};
} catch(error) {frame.remove();throw error;}
