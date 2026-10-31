var V=globalThis,W=V.ShadowRoot&&(V.ShadyCSS===void 0||V.ShadyCSS.nativeShadow)&&"adoptedStyleSheets"in Document.prototype&&"replace"in CSSStyleSheet.prototype,Q=Symbol(),ge=new WeakMap,H=class{constructor(e,t,n){if(this._$cssResult$=!0,n!==Q)throw Error("CSSResult is not constructable. Use `unsafeCSS` or `css` instead.");this.cssText=e,this.t=t}get styleSheet(){let e=this.o,t=this.t;if(W&&e===void 0){let n=t!==void 0&&t.length===1;n&&(e=ge.get(t)),e===void 0&&((this.o=e=new CSSStyleSheet).replaceSync(this.cssText),n&&ge.set(t,e))}return e}toString(){return this.cssText}},_e=i=>new H(typeof i=="string"?i:i+"",void 0,Q),g=(i,...e)=>{let t=i.length===1?i[0]:e.reduce((n,o,s)=>n+(r=>{if(r._$cssResult$===!0)return r.cssText;if(typeof r=="number")return r;throw Error("Value passed to 'css' function must be a 'css' function result: "+r+". Use 'unsafeCSS' to pass non-literal values, but take care to ensure page security.")})(o)+i[s+1],i[0]);return new H(t,i,Q)},ve=(i,e)=>{if(W)i.adoptedStyleSheets=e.map(t=>t instanceof CSSStyleSheet?t:t.styleSheet);else for(let t of e){let n=document.createElement("style"),o=V.litNonce;o!==void 0&&n.setAttribute("nonce",o),n.textContent=t.cssText,i.appendChild(n)}},ee=W?i=>i:i=>i instanceof CSSStyleSheet?(e=>{let t="";for(let n of e.cssRules)t+=n.cssText;return _e(t)})(i):i;var{is:mt,defineProperty:pt,getOwnPropertyDescriptor:ft,getOwnPropertyNames:yt,getOwnPropertySymbols:gt,getPrototypeOf:_t}=Object,z=globalThis,we=z.trustedTypes,vt=we?we.emptyScript:"",wt=z.reactiveElementPolyfillSupport,R=(i,e)=>i,te={toAttribute(i,e){switch(e){case Boolean:i=i?vt:null;break;case Object:case Array:i=i==null?i:JSON.stringify(i)}return i},fromAttribute(i,e){let t=i;switch(e){case Boolean:t=i!==null;break;case Number:t=i===null?null:Number(i);break;case Object:case Array:try{t=JSON.parse(i)}catch{t=null}}return t}},$e=(i,e)=>!mt(i,e),be={attribute:!0,type:String,converter:te,reflect:!1,useDefault:!1,hasChanged:$e};Symbol.metadata??=Symbol("metadata"),z.litPropertyMetadata??=new WeakMap;var v=class extends HTMLElement{static addInitializer(e){this._$Ei(),(this.l??=[]).push(e)}static get observedAttributes(){return this.finalize(),this._$Eh&&[...this._$Eh.keys()]}static createProperty(e,t=be){if(t.state&&(t.attribute=!1),this._$Ei(),this.prototype.hasOwnProperty(e)&&((t=Object.create(t)).wrapped=!0),this.elementProperties.set(e,t),!t.noAccessor){let n=Symbol(),o=this.getPropertyDescriptor(e,n,t);o!==void 0&&pt(this.prototype,e,o)}}static getPropertyDescriptor(e,t,n){let{get:o,set:s}=ft(this.prototype,e)??{get(){return this[t]},set(r){this[t]=r}};return{get:o,set(r){let c=o?.call(this);s?.call(this,r),this.requestUpdate(e,c,n)},configurable:!0,enumerable:!0}}static getPropertyOptions(e){return this.elementProperties.get(e)??be}static _$Ei(){if(this.hasOwnProperty(R("elementProperties")))return;let e=_t(this);e.finalize(),e.l!==void 0&&(this.l=[...e.l]),this.elementProperties=new Map(e.elementProperties)}static finalize(){if(this.hasOwnProperty(R("finalized")))return;if(this.finalized=!0,this._$Ei(),this.hasOwnProperty(R("properties"))){let t=this.properties,n=[...yt(t),...gt(t)];for(let o of n)this.createProperty(o,t[o])}let e=this[Symbol.metadata];if(e!==null){let t=litPropertyMetadata.get(e);if(t!==void 0)for(let[n,o]of t)this.elementProperties.set(n,o)}this._$Eh=new Map;for(let[t,n]of this.elementProperties){let o=this._$Eu(t,n);o!==void 0&&this._$Eh.set(o,t)}this.elementStyles=this.finalizeStyles(this.styles)}static finalizeStyles(e){let t=[];if(Array.isArray(e)){let n=new Set(e.flat(1/0).reverse());for(let o of n)t.unshift(ee(o))}else e!==void 0&&t.push(ee(e));return t}static _$Eu(e,t){let n=t.attribute;return n===!1?void 0:typeof n=="string"?n:typeof e=="string"?e.toLowerCase():void 0}constructor(){super(),this._$Ep=void 0,this.isUpdatePending=!1,this.hasUpdated=!1,this._$Em=null,this._$Ev()}_$Ev(){this._$ES=new Promise(e=>this.enableUpdating=e),this._$AL=new Map,this._$E_(),this.requestUpdate(),this.constructor.l?.forEach(e=>e(this))}addController(e){(this._$EO??=new Set).add(e),this.renderRoot!==void 0&&this.isConnected&&e.hostConnected?.()}removeController(e){this._$EO?.delete(e)}_$E_(){let e=new Map,t=this.constructor.elementProperties;for(let n of t.keys())this.hasOwnProperty(n)&&(e.set(n,this[n]),delete this[n]);e.size>0&&(this._$Ep=e)}createRenderRoot(){let e=this.shadowRoot??this.attachShadow(this.constructor.shadowRootOptions);return ve(e,this.constructor.elementStyles),e}connectedCallback(){this.renderRoot??=this.createRenderRoot(),this.enableUpdating(!0),this._$EO?.forEach(e=>e.hostConnected?.())}enableUpdating(e){}disconnectedCallback(){this._$EO?.forEach(e=>e.hostDisconnected?.())}attributeChangedCallback(e,t,n){this._$AK(e,n)}_$ET(e,t){let n=this.constructor.elementProperties.get(e),o=this.constructor._$Eu(e,n);if(o!==void 0&&n.reflect===!0){let s=(n.converter?.toAttribute!==void 0?n.converter:te).toAttribute(t,n.type);this._$Em=e,s==null?this.removeAttribute(o):this.setAttribute(o,s),this._$Em=null}}_$AK(e,t){let n=this.constructor,o=n._$Eh.get(e);if(o!==void 0&&this._$Em!==o){let s=n.getPropertyOptions(o),r=typeof s.converter=="function"?{fromAttribute:s.converter}:s.converter?.fromAttribute!==void 0?s.converter:te;this._$Em=o;let c=r.fromAttribute(t,s.type);this[o]=c??this._$Ej?.get(o)??c,this._$Em=null}}requestUpdate(e,t,n,o=!1,s){if(e!==void 0){let r=this.constructor;if(o===!1&&(s=this[e]),n??=r.getPropertyOptions(e),!((n.hasChanged??$e)(s,t)||n.useDefault&&n.reflect&&s===this._$Ej?.get(e)&&!this.hasAttribute(r._$Eu(e,n))))return;this.C(e,t,n)}this.isUpdatePending===!1&&(this._$ES=this._$EP())}C(e,t,{useDefault:n,reflect:o,wrapped:s},r){n&&!(this._$Ej??=new Map).has(e)&&(this._$Ej.set(e,r??t??this[e]),s!==!0||r!==void 0)||(this._$AL.has(e)||(this.hasUpdated||n||(t=void 0),this._$AL.set(e,t)),o===!0&&this._$Em!==e&&(this._$Eq??=new Set).add(e))}async _$EP(){this.isUpdatePending=!0;try{await this._$ES}catch(t){Promise.reject(t)}let e=this.scheduleUpdate();return e!=null&&await e,!this.isUpdatePending}scheduleUpdate(){return this.performUpdate()}performUpdate(){if(!this.isUpdatePending)return;if(!this.hasUpdated){if(this.renderRoot??=this.createRenderRoot(),this._$Ep){for(let[o,s]of this._$Ep)this[o]=s;this._$Ep=void 0}let n=this.constructor.elementProperties;if(n.size>0)for(let[o,s]of n){let{wrapped:r}=s,c=this[o];r!==!0||this._$AL.has(o)||c===void 0||this.C(o,void 0,s,c)}}let e=!1,t=this._$AL;try{e=this.shouldUpdate(t),e?(this.willUpdate(t),this._$EO?.forEach(n=>n.hostUpdate?.()),this.update(t)):this._$EM()}catch(n){throw e=!1,this._$EM(),n}e&&this._$AE(t)}willUpdate(e){}_$AE(e){this._$EO?.forEach(t=>t.hostUpdated?.()),this.hasUpdated||(this.hasUpdated=!0,this.firstUpdated(e)),this.updated(e)}_$EM(){this._$AL=new Map,this.isUpdatePending=!1}get updateComplete(){return this.getUpdateComplete()}getUpdateComplete(){return this._$ES}shouldUpdate(e){return!0}update(e){this._$Eq&&=this._$Eq.forEach(t=>this._$ET(t,this[t])),this._$EM()}updated(e){}firstUpdated(e){}};v.elementStyles=[],v.shadowRootOptions={mode:"open"},v[R("elementProperties")]=new Map,v[R("finalized")]=new Map,wt?.({ReactiveElement:v}),(z.reactiveElementVersions??=[]).push("2.1.2");var de=globalThis,Ae=i=>i,B=de.trustedTypes,ke=B?B.createPolicy("lit-html",{createHTML:i=>i}):void 0,Pe="$lit$",b=`lit$${Math.random().toFixed(9).slice(2)}$`,He="?"+b,bt=`<${He}>`,T=document,O=()=>T.createComment(""),U=i=>i===null||typeof i!="object"&&typeof i!="function",le=Array.isArray,$t=i=>le(i)||typeof i?.[Symbol.iterator]=="function",ne=`[ 	
\f\r]`,M=/<(?:(!--|\/[^a-zA-Z])|(\/?[a-zA-Z][^>\s]*)|(\/?$))/g,Te=/-->/g,xe=/>/g,A=RegExp(`>|${ne}(?:([^\\s"'>=/]+)(${ne}*=${ne}*(?:[^ 	
\f\r"'\`<>=]|("|')|))|$)`,"g"),Ce=/'/g,Se=/"/g,Re=/^(?:script|style|textarea|title)$/i,ce=i=>(e,...t)=>({_$litType$:i,strings:e,values:t}),m=ce(1),Gt=ce(2),Yt=ce(3),w=Symbol.for("lit-noChange"),l=Symbol.for("lit-nothing"),Ee=new WeakMap,k=T.createTreeWalker(T,129);function Me(i,e){if(!le(i)||!i.hasOwnProperty("raw"))throw Error("invalid template strings array");return ke!==void 0?ke.createHTML(e):e}var At=(i,e)=>{let t=i.length-1,n=[],o,s=e===2?"<svg>":e===3?"<math>":"",r=M;for(let c=0;c<t;c++){let a=i[c],h,u,d=-1,f=0;for(;f<a.length&&(r.lastIndex=f,u=r.exec(a),u!==null);)f=r.lastIndex,r===M?u[1]==="!--"?r=Te:u[1]!==void 0?r=xe:u[2]!==void 0?(Re.test(u[2])&&(o=RegExp("</"+u[2],"g")),r=A):u[3]!==void 0&&(r=A):r===A?u[0]===">"?(r=o??M,d=-1):u[1]===void 0?d=-2:(d=r.lastIndex-u[2].length,h=u[1],r=u[3]===void 0?A:u[3]==='"'?Se:Ce):r===Se||r===Ce?r=A:r===Te||r===xe?r=M:(r=A,o=void 0);let y=r===A&&i[c+1].startsWith("/>")?" ":"";s+=r===M?a+bt:d>=0?(n.push(h),a.slice(0,d)+Pe+a.slice(d)+b+y):a+b+(d===-2?c:y)}return[Me(i,s+(i[t]||"<?>")+(e===2?"</svg>":e===3?"</math>":"")),n]},D=class i{constructor({strings:e,_$litType$:t},n){let o;this.parts=[];let s=0,r=0,c=e.length-1,a=this.parts,[h,u]=At(e,t);if(this.el=i.createElement(h,n),k.currentNode=this.el.content,t===2||t===3){let d=this.el.content.firstChild;d.replaceWith(...d.childNodes)}for(;(o=k.nextNode())!==null&&a.length<c;){if(o.nodeType===1){if(o.hasAttributes())for(let d of o.getAttributeNames())if(d.endsWith(Pe)){let f=u[r++],y=o.getAttribute(d).split(b),$=/([.?@])?(.*)/.exec(f);a.push({type:1,index:s,name:$[2],strings:y,ctor:$[1]==="."?oe:$[1]==="?"?se:$[1]==="@"?re:S}),o.removeAttribute(d)}else d.startsWith(b)&&(a.push({type:6,index:s}),o.removeAttribute(d));if(Re.test(o.tagName)){let d=o.textContent.split(b),f=d.length-1;if(f>0){o.textContent=B?B.emptyScript:"";for(let y=0;y<f;y++)o.append(d[y],O()),k.nextNode(),a.push({type:2,index:++s});o.append(d[f],O())}}}else if(o.nodeType===8)if(o.data===He)a.push({type:2,index:s});else{let d=-1;for(;(d=o.data.indexOf(b,d+1))!==-1;)a.push({type:7,index:s}),d+=b.length-1}s++}}static createElement(e,t){let n=T.createElement("template");return n.innerHTML=e,n}};function C(i,e,t=i,n){if(e===w)return e;let o=n!==void 0?t._$Co?.[n]:t._$Cl,s=U(e)?void 0:e._$litDirective$;return o?.constructor!==s&&(o?._$AO?.(!1),s===void 0?o=void 0:(o=new s(i),o._$AT(i,t,n)),n!==void 0?(t._$Co??=[])[n]=o:t._$Cl=o),o!==void 0&&(e=C(i,o._$AS(i,e.values),o,n)),e}var ie=class{constructor(e,t){this._$AV=[],this._$AN=void 0,this._$AD=e,this._$AM=t}get parentNode(){return this._$AM.parentNode}get _$AU(){return this._$AM._$AU}u(e){let{el:{content:t},parts:n}=this._$AD,o=(e?.creationScope??T).importNode(t,!0);k.currentNode=o;let s=k.nextNode(),r=0,c=0,a=n[0];for(;a!==void 0;){if(r===a.index){let h;a.type===2?h=new N(s,s.nextSibling,this,e):a.type===1?h=new a.ctor(s,a.name,a.strings,this,e):a.type===6&&(h=new ae(s,this,e)),this._$AV.push(h),a=n[++c]}r!==a?.index&&(s=k.nextNode(),r++)}return k.currentNode=T,o}p(e){let t=0;for(let n of this._$AV)n!==void 0&&(n.strings!==void 0?(n._$AI(e,n,t),t+=n.strings.length-2):n._$AI(e[t])),t++}},N=class i{get _$AU(){return this._$AM?._$AU??this._$Cv}constructor(e,t,n,o){this.type=2,this._$AH=l,this._$AN=void 0,this._$AA=e,this._$AB=t,this._$AM=n,this.options=o,this._$Cv=o?.isConnected??!0}get parentNode(){let e=this._$AA.parentNode,t=this._$AM;return t!==void 0&&e?.nodeType===11&&(e=t.parentNode),e}get startNode(){return this._$AA}get endNode(){return this._$AB}_$AI(e,t=this){e=C(this,e,t),U(e)?e===l||e==null||e===""?(this._$AH!==l&&this._$AR(),this._$AH=l):e!==this._$AH&&e!==w&&this._(e):e._$litType$!==void 0?this.$(e):e.nodeType!==void 0?this.T(e):$t(e)?this.k(e):this._(e)}O(e){return this._$AA.parentNode.insertBefore(e,this._$AB)}T(e){this._$AH!==e&&(this._$AR(),this._$AH=this.O(e))}_(e){this._$AH!==l&&U(this._$AH)?this._$AA.nextSibling.data=e:this.T(T.createTextNode(e)),this._$AH=e}$(e){let{values:t,_$litType$:n}=e,o=typeof n=="number"?this._$AC(e):(n.el===void 0&&(n.el=D.createElement(Me(n.h,n.h[0]),this.options)),n);if(this._$AH?._$AD===o)this._$AH.p(t);else{let s=new ie(o,this),r=s.u(this.options);s.p(t),this.T(r),this._$AH=s}}_$AC(e){let t=Ee.get(e.strings);return t===void 0&&Ee.set(e.strings,t=new D(e)),t}k(e){le(this._$AH)||(this._$AH=[],this._$AR());let t=this._$AH,n,o=0;for(let s of e)o===t.length?t.push(n=new i(this.O(O()),this.O(O()),this,this.options)):n=t[o],n._$AI(s),o++;o<t.length&&(this._$AR(n&&n._$AB.nextSibling,o),t.length=o)}_$AR(e=this._$AA.nextSibling,t){for(this._$AP?.(!1,!0,t);e!==this._$AB;){let n=Ae(e).nextSibling;Ae(e).remove(),e=n}}setConnected(e){this._$AM===void 0&&(this._$Cv=e,this._$AP?.(e))}},S=class{get tagName(){return this.element.tagName}get _$AU(){return this._$AM._$AU}constructor(e,t,n,o,s){this.type=1,this._$AH=l,this._$AN=void 0,this.element=e,this.name=t,this._$AM=o,this.options=s,n.length>2||n[0]!==""||n[1]!==""?(this._$AH=Array(n.length-1).fill(new String),this.strings=n):this._$AH=l}_$AI(e,t=this,n,o){let s=this.strings,r=!1;if(s===void 0)e=C(this,e,t,0),r=!U(e)||e!==this._$AH&&e!==w,r&&(this._$AH=e);else{let c=e,a,h;for(e=s[0],a=0;a<s.length-1;a++)h=C(this,c[n+a],t,a),h===w&&(h=this._$AH[a]),r||=!U(h)||h!==this._$AH[a],h===l?e=l:e!==l&&(e+=(h??"")+s[a+1]),this._$AH[a]=h}r&&!o&&this.j(e)}j(e){e===l?this.element.removeAttribute(this.name):this.element.setAttribute(this.name,e??"")}},oe=class extends S{constructor(){super(...arguments),this.type=3}j(e){this.element[this.name]=e===l?void 0:e}},se=class extends S{constructor(){super(...arguments),this.type=4}j(e){this.element.toggleAttribute(this.name,!!e&&e!==l)}},re=class extends S{constructor(e,t,n,o,s){super(e,t,n,o,s),this.type=5}_$AI(e,t=this){if((e=C(this,e,t,0)??l)===w)return;let n=this._$AH,o=e===l&&n!==l||e.capture!==n.capture||e.once!==n.once||e.passive!==n.passive,s=e!==l&&(n===l||o);o&&this.element.removeEventListener(this.name,this,n),s&&this.element.addEventListener(this.name,this,e),this._$AH=e}handleEvent(e){typeof this._$AH=="function"?this._$AH.call(this.options?.host??this.element,e):this._$AH.handleEvent(e)}},ae=class{constructor(e,t,n){this.element=e,this.type=6,this._$AN=void 0,this._$AM=t,this.options=n}get _$AU(){return this._$AM._$AU}_$AI(e){C(this,e)}};var kt=de.litHtmlPolyfillSupport;kt?.(D,N),(de.litHtmlVersions??=[]).push("3.3.3");var Oe=(i,e,t)=>{let n=t?.renderBefore??e,o=n._$litPart$;if(o===void 0){let s=t?.renderBefore??null;n._$litPart$=o=new N(e.insertBefore(O(),s),s,void 0,t??{})}return o._$AI(i),o};var he=globalThis,_=class extends v{constructor(){super(...arguments),this.renderOptions={host:this},this._$Do=void 0}createRenderRoot(){let e=super.createRenderRoot();return this.renderOptions.renderBefore??=e.firstChild,e}update(e){let t=this.render();this.hasUpdated||(this.renderOptions.isConnected=this.isConnected),super.update(e),this._$Do=Oe(t,this.renderRoot,this.renderOptions)}connectedCallback(){super.connectedCallback(),this._$Do?.setConnected(!0)}disconnectedCallback(){super.disconnectedCallback(),this._$Do?.setConnected(!1)}render(){return w}};_._$litElement$=!0,_.finalized=!0,he.litElementHydrateSupport?.({LitElement:_});var Tt=he.litElementPolyfillSupport;Tt?.({LitElement:_});(he.litElementVersions??=[]).push("4.2.2");async function ue(i,e,t,n,o){try{await i.callService(e,t,n,{entity_id:o})}catch{}}function Ue(i,e,t){return ue(i,"number","set_value",{value:t},e)}function De(i,e,t){return ue(i,"timerify","add_time",{minutes:t},e)}function Ne(i,e){return ue(i,"timerify","run",{},e)}var Ie={card_entity_not_found:"Entity not found: {entity}",card_not_a_timer:"{entity} is not the Run for number of a Timerify timer",card_error_entity:"Choose the Run for number of a timer",card_error_layout:"The layout is pill or round",card_error_presets:"Presets are whole minutes from 1 to 1440",card_error_chip:"The quick chip is whole minutes from 1 to 1440",card_close:"Close",card_until:"until {time}",card_add_time:"Add {duration}",card_picker_description:"The countdown, presets and schedule of a Timerify timer"};var Ve="common",We="timerify",Ct=`component.${We}.${Ve}.`;function St(i,e){return i.replace(/\{(\w+)\}/g,(t,n)=>String(e?.[n]??t))}function p(i,e,t){return i?.localize(Ct+e,t)||St(Ie[e],t)}var I,Le=Promise.resolve(),ze,Be=new Set;function je(i){return i.language!==I&&(I=i.language,Le=Et(i,i.language)),Le}async function Et(i,e){let t;try{t=await i.loadBackendTranslation(Ve,We)}catch{I===e&&(I=void 0);return}I===e&&(ze={...i,localize:t},Be.forEach(n=>n()))}function j(){return ze}function Fe(i){Be.add(i)}var Pt=[15,30,45,60,120],Ht=1440,x=class extends Error{constructor(t){super(p(j(),t));this.key=t}key};function Ke(i){let e=typeof i=="number"?i:typeof i=="string"&&/^\d+$/.test(i)?Number(i):void 0;return e!==void 0&&Number.isInteger(e)&&e>=1&&e<=Ht?e:void 0}function Rt(i){if(i===void 0)return[...Pt];if(!Array.isArray(i)||i.length===0)throw new x("card_error_presets");let e=new Set;for(let t of i){let n=Ke(t);if(n===void 0)throw new x("card_error_presets");e.add(n)}return[...e]}function Mt(i){if(i===void 0)return;let e=Ke(i);if(e===void 0)throw new x("card_error_chip");return e}function qe(i){let e=typeof i=="object"&&i!==null?i:{},{entity:t,layout:n="pill",name:o,icon:s}=e;if(typeof t!="string"||!/^number\.[a-z0-9_]+$/.test(t))throw new x("card_error_entity");if(n!=="pill"&&n!=="round")throw new x("card_error_layout");let r=Mt(e.chip);return{entity:t,layout:n,...typeof o=="string"&&o!==""&&{name:o},...typeof s=="string"&&s!==""&&{icon:s},presets:Rt(e.presets),...r!==void 0&&{chip:r}}}var F=class{#e;#n;#i=!1;#t;constructor(e,t){this.#e=e,this.#n=t,e.addController(this)}hostConnected(){this.#i=!0,this.#o()}hostUpdated(){this.#o()}hostDisconnected(){this.#i=!1,this.#o()}#o(){let e=this.#n(),t=this.#i&&e!==void 0&&e.getTime()>Date.now();t&&this.#t===void 0?this.#t=setInterval(()=>this.#e.requestUpdate(),1e3):!t&&this.#t!==void 0&&(clearInterval(this.#t),this.#t=void 0)}};var Ge=i=>String(i).padStart(2,"0");function K(i){let e=Math.ceil(Math.max(0,i)),t=Math.floor(e/3600),n=Math.floor(e%3600/60),o=Ge(e%60);return t>0?`${t}:${Ge(n)}:${o}`:`${n}:${o}`}function Ot({language:i,time_format:e}){if(e==="12"||e==="24")return e==="12";let t=new Intl.DateTimeFormat(e==="language"?i:void 0,{hour:"numeric"}).resolvedOptions();return t.hourCycle==="h11"||t.hourCycle==="h12"}var Ut=864e5;function Ye(i,e){let t=new Intl.DateTimeFormat("en-US",{timeZone:i,year:"numeric",month:"numeric",day:"numeric"}).formatToParts(e),n=o=>Number(t.find(s=>s.type===o)?.value);return Date.UTC(n("year"),n("month")-1,n("day"))/Ut}function Ze(i,e,t){let{locale:n}=i,o=n.time_zone==="server"?i.config.time_zone:void 0,s=Ye(o,e.getTime())-Ye(o,t),r=s===0?{}:s>=1&&s<=6?{weekday:"short"}:{month:"short",day:"numeric"};return new Intl.DateTimeFormat(n.language,{...r,hour:"numeric",minute:"2-digit",hourCycle:Ot(n)?"h12":"h23",timeZone:o}).format(e)}function me(i,e){let t=(r,c)=>new Intl.NumberFormat(i.locale.language,{style:"unit",unit:c,unitDisplay:"short",useGrouping:!1}).format(r),n=Math.floor(e/60),o=e%60,s=n>0?[t(n,"hour")]:[];return(o>0||n===0)&&s.push(t(o,"minute")),s.join(" ")}var Dt="not_found";async function Qe(i,e){try{return{status:"found",info:await i.callWS({type:"timerify/timer",entity_id:e})}}catch(t){return{status:typeof t=="object"&&t!==null&&"code"in t&&t.code===Dt?"not_found":"failed"}}}var E=i=>i!==void 0&&i.state!=="unavailable"&&i.state!=="unknown";function Nt(i,e){return i===void 0||i.state==="unavailable"||i.state==="unknown"?!1:e.states.includes(i.state)===(e.match==="is")}var It="mdi:timer-outline",Je=i=>i===void 0||i.state==="unavailable";function Xe(i){let e=typeof i=="string"?Date.parse(i):Number.NaN;return Number.isNaN(e)?void 0:e}function et(i,e,t,n){let o=t.status==="found"?t.info:void 0,s=i.states[e.entity],r=o&&i.states[o.target],c=e.name||r&&i.formatEntityName(r,void 0)||s?.attributes.friendly_name||e.entity,a=e.icon?{icon:e.icon}:r?{stateObj:r}:{icon:It},h={name:c,icon:a,target:r,remaining:0},u=o&&i.states[o.ends_at];if(o===void 0||u===void 0||Je(s)||Je(u))return{...h,state:"unavailable",progress:0};let d=Xe(u.state);if(d===void 0)return Nt(r,o.target_on)?{...h,state:"open",progress:1}:{...h,state:"idle",progress:0};let f=Xe(u.attributes.started_at),y=f===void 0?0:(d-f)/1e3,$=Math.max(0,(d-n)/1e3);return{...h,state:"counting",remaining:$,progress:y>0?Math.min(1,$/y):1,endsAt:new Date(d)}}function q(i,e){return e?[i,e.ends_at,e.next_command,e.target,...e.intervals.map(({entity_id:t})=>t)]:[i]}var Lt=["locale","language","localize","config","user","connected","entities"];function G(i,e,t){for(let o of i.keys())if(o!=="hass")return!0;let n=i.get("hass");return n===void 0||e===void 0?!0:Lt.some(o=>n[o]!==e[o])||t.some(o=>n.states[o]!==e.states[o])}function Y(i){return"stateObj"in i.icon?m`<ha-state-icon .stateObj=${i.icon.stateObj}></ha-state-icon>`:m`<ha-icon .icon=${i.icon.icon}></ha-icon>`}function Vt(i,e,t){if(i.state!=="unavailable")return i.target?t.formatEntityState(i.target):"";let n=t.states[e.entity];if(E(n))return"";let o={entity_id:e.entity,state:"unavailable",attributes:{}};return t.formatEntityState(n??o,"unavailable")}function Z(i,e,t,n){if(i.state!=="counting"||i.endsAt===void 0)return Vt(i,e,t);let o=Ze(t,i.endsAt,n);return m`
    <span class="remaining">${K(i.remaining)}</span>
    <span class="until">${p(t,"card_until",{time:o})}</span>
  `}var tt=g`
  /*
   * A long touch must bring up neither a text selection nor the browser's callout. The text
   * is in the content, not in the body, so the rule is on the card, and so on all it holds;
   * the pop-up is beside the card, and its text stays selectable.
   */
  ha-card.pill,
  ha-card.round {
    user-select: none;
    -webkit-user-select: none;
    -webkit-touch-callout: none;
  }
  .body {
    position: absolute;
    inset: 0;
    /* Inset reaches the padding box; the card's border is part of what a press hits. */
    margin: calc(-1 * var(--ha-card-border-width, 1px));
    border-radius: var(--timerify-radius);
    cursor: pointer;
    /* No flash of the browser's own highlight on a tap, as in the tile card. */
    -webkit-tap-highlight-color: transparent;
  }
  .body:focus-visible {
    outline: 2px solid var(--primary-color);
    outline-offset: 2px;
  }
  .content {
    position: relative;
    box-sizing: border-box;
    height: 100%;
    /* A press anywhere on the card reaches the body underneath, except on a control. */
    pointer-events: none;
  }
  .icon {
    color: var(--state-icon-color, var(--secondary-text-color));
  }
  .counting .icon,
  .open .icon {
    color: var(--state-active-color, var(--primary-color));
  }
  .unavailable .icon {
    color: var(--state-unavailable-color, var(--disabled-text-color));
  }
  .name {
    overflow: hidden;
    color: var(--primary-text-color);
    font-size: var(--ha-font-size-m, 14px);
    font-weight: var(--ha-font-weight-medium, 500);
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .remaining {
    font-variant-numeric: tabular-nums;
  }
`;var nt={ATTRIBUTE:1,CHILD:2,PROPERTY:3,BOOLEAN_ATTRIBUTE:4,EVENT:5,ELEMENT:6},it=i=>(...e)=>({_$litDirective$:i,values:e}),J=class{constructor(e){}get _$AU(){return this._$AM._$AU}_$AT(e,t,n){this._$Ct=e,this._$AM=t,this._$Ci=n}_$AS(e,t){return this.update(e,t)}update(e,t){return this.render(...t)}};var ot="important",Wt=" !"+ot,st=it(class extends J{constructor(i){if(super(i),i.type!==nt.ATTRIBUTE||i.name!=="style"||i.strings?.length>2)throw Error("The `styleMap` directive must be used in the `style` attribute and must be the only part in the attribute.")}render(i){return Object.keys(i).reduce((e,t)=>{let n=i[t];return n==null?e:e+`${t=t.includes("-")?t:t.replace(/(?:^(webkit|moz|ms|o)|)(?=[A-Z])/g,"-$&").toLowerCase()}:${n};`},"")}update(i,[e]){let{style:t}=i.element;if(this.ft===void 0)return this.ft=new Set(Object.keys(e)),this.render(e);for(let n of this.ft)e[n]==null&&(this.ft.delete(n),n.includes("-")?t.removeProperty(n):t[n]=null);for(let n in e){let o=e[n];if(o!=null){this.ft.add(n);let s=typeof o=="string"&&o.endsWith(Wt);n.includes("-")||s?t.setProperty(n,s?o.slice(0,-11):o,s?ot:""):t[n]=o}}return w}});function rt(i,e,t,n,o,s){let r=Math.round(i.progress*1e3)/10;return m`
    <ha-card class="pill ${i.state}">
      <div
        class="body"
        role="button"
        tabindex="0"
        aria-haspopup="dialog"
        aria-labelledby="label"
        @click=${n.click}
        @keydown=${n.keydown}
        @keyup=${n.keyup}
      >
        <span class="fill-clip" aria-hidden="true">
          <span class="fill" style=${st({width:`${r}%`})}></span>
        </span>
      </div>
      <div class="content">
        <span class="icon">${Y(i)}</span>
        <span class="text" id="label">
          <span class="name">${i.name}</span>
          <span class="status">${Z(i,e,t,s)}</span>
        </span>
        ${e.chip===void 0?l:m`
              <button
                class="chip"
                type="button"
                aria-label=${p(t,"card_add_time",{duration:me(t,e.chip)})}
                @click=${o}
              >
                +${me(t,e.chip)}
              </button>
            `}
      </div>
    </ha-card>
  `}var at=g`
  ha-card.pill {
    --timerify-radius: 28px;
    height: 56px;
    border-radius: var(--timerify-radius);
  }
  .fill-clip {
    position: absolute;
    inset: 0;
    overflow: hidden;
    border-radius: var(--timerify-radius);
  }
  .fill {
    display: block;
    height: 100%;
    background: var(--state-active-color, var(--primary-color));
    opacity: 0.3;
  }
  .pill .content {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 0 12px 0 8px;
  }
  .pill .icon {
    display: flex;
    flex: none;
    align-items: center;
    justify-content: center;
    width: 40px;
    height: 40px;
  }
  .pill .text {
    display: flex;
    flex: 1 1 auto;
    flex-direction: column;
    min-width: 0;
  }
  .pill .status {
    display: flex;
    gap: 6px;
    overflow: hidden;
    color: var(--secondary-text-color);
    font-size: var(--ha-font-size-s, 12px);
    white-space: nowrap;
  }
  .chip {
    flex: none;
    height: 32px;
    padding: 0 12px;
    border: none;
    border-radius: 16px;
    background: var(--secondary-background-color);
    color: var(--primary-text-color);
    font: inherit;
    font-size: var(--ha-font-size-m, 14px);
    cursor: pointer;
    pointer-events: auto;
  }
  .chip:focus-visible {
    outline: 2px solid var(--primary-color);
    outline-offset: 2px;
  }
`;var X=class extends _{static properties={hass:{attribute:!1},config:{attribute:!1},info:{attribute:!1},view:{attribute:!1},opened:{state:!0}};static styles=g`
    dialog {
      box-sizing: border-box;
      width: 100%;
      max-width: 420px;
      padding: 0;
      border: none;
      border-radius: var(--ha-border-radius-lg, 16px);
      background: var(--card-background-color);
      color: var(--primary-text-color);
    }
    dialog::backdrop {
      background: rgba(0, 0, 0, 0.4);
    }
    @media (max-width: 450px) {
      dialog {
        max-width: 100%;
      }
    }
    .wrapper {
      padding: 16px;
    }
    header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 8px;
    }
    h2 {
      margin: 0;
      font-size: var(--ha-font-size-xl, 1.25rem);
      font-weight: 500;
    }
    button.close {
      padding: 8px 12px;
      border: none;
      border-radius: var(--ha-border-radius-md, 8px);
      background: none;
      color: var(--primary-color);
      font: inherit;
      cursor: pointer;
    }
    button.close:focus-visible {
      outline: 2px solid var(--primary-color);
      outline-offset: 2px;
    }
  `;constructor(){super(),this.opened=!1}open(){this.opened=!0}close(){this.#e?.close(),this.#i()}disconnectedCallback(){super.disconnectedCallback(),this.close()}get#e(){return this.renderRoot.querySelector("dialog")}#n=()=>{this.#e?.open||this.#i()};#i(){this.opened&&(this.opened=!1,this.dispatchEvent(new CustomEvent("closed")))}shouldUpdate(e){if(!this.hasUpdated||e.has("opened"))return!0;let t=q(this.config.entity,this.info);return this.opened&&G(e,this.hass,t)}updated(e){let t=this.#e;e.has("opened")&&this.opened&&t&&!t.open&&t.showModal()}render(){return m`
      <dialog
        aria-labelledby="title"
        @cancel=${()=>this.close()}
        @close=${this.#n}
        @click=${e=>{e.target===e.currentTarget&&this.close()}}
      >
        ${this.opened?this.#t():l}
      </dialog>
    `}#t(){return m`
      <div class="wrapper">
        <header>
          <h2 id="title">${this.view.name}</h2>
          <button class="close" @click=${()=>this.close()}>
            ${p(this.hass,"card_close")}
          </button>
        </header>
      </div>
    `}};var dt="data-held",L=class{#e;#n;#i=!1;#t;#o;#d=!1;#s=!1;constructor(e,t){this.#e=e,this.#n=t,e.addController(this)}hostDisconnected(){this.#i=!1,this.#s=!1,this.#r()}binding(){let e={click:n=>{if(this.#s){this.#s=!1,n.preventDefault(),n.stopPropagation();return}this.#n.tap()},keydown:n=>{n.key==="Enter"?(n.preventDefault(),n.repeat||this.#n.tap()):n.key===" "&&(n.preventDefault(),this.#i=!0)},keyup:n=>{if(n.key!==" ")return;let o=this.#i;this.#i=!1,o&&this.#n.tap()}},{hold:t}=this.#n;return t===void 0?e:{...e,pointerdown:n=>this.#a(n),pointerup:n=>{if(n.pointerId!==this.#t)return;let o=this.#d;this.#r(),o&&(this.#s=!0,t())},pointercancel:n=>this.#l(n),pointerleave:n=>this.#l(n),contextmenu:n=>{this.#t!==void 0&&n.preventDefault()}}}#a(e){!e.isPrimary||e.button!==0||(this.#s=!1,this.#r(),this.#t=e.pointerId,this.#o=setTimeout(()=>{this.#o=void 0,this.#d=!0,this.#e.setAttribute(dt,"")},500))}#l(e){e.pointerId===this.#t&&this.#r()}#r(){clearTimeout(this.#o),this.#o=void 0,this.#t=void 0,this.#d=!1,this.#e.removeAttribute(dt)}};var P=80,ct=6,pe=(P-ct)/2,lt=2*Math.PI*pe;function zt(i){if(i.state!=="counting")return m`<span class="icon">${Y(i)}</span>`;let e=K(i.remaining);return m`<span class="time" aria-hidden="true">${e}</span>`}function ht(i,e,t,n,o){let s=P/2;return m`
    <ha-card class="round ${i.state}">
      <div
        class="body"
        role="button"
        tabindex="0"
        aria-haspopup="dialog"
        aria-labelledby="label"
        @click=${n.click}
        @keydown=${n.keydown}
        @keyup=${n.keyup}
        @pointerdown=${n.pointerdown}
        @pointerup=${n.pointerup}
        @pointercancel=${n.pointercancel}
        @pointerleave=${n.pointerleave}
        @contextmenu=${n.contextmenu}
      ></div>
      <div class="content">
        <div class="dial">
          <svg class="ring" viewBox="0 0 ${P} ${P}" aria-hidden="true">
            <circle class="track" cx=${s} cy=${s} r=${pe}></circle>
            <circle
              class="progress"
              cx=${s}
              cy=${s}
              r=${pe}
              transform="rotate(-90 ${s} ${s})"
              stroke-dasharray=${lt}
              stroke-dashoffset=${(1-i.progress)*lt}
            ></circle>
          </svg>
          <span class="centre">
            ${zt(i)}
          </span>
        </div>
        <span class="text" id="label">
          <span class="name">${i.name}</span>
          <span class="status">${Z(i,e,t,o)}</span>
        </span>
      </div>
    </ha-card>
  `}var ut=g`
  ha-card.round {
    --timerify-radius: var(--ha-card-border-radius, var(--ha-border-radius-lg, 12px));
    height: 120px;
  }
  .round .content {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 4px;
    padding: 8px;
  }
  .dial {
    position: relative;
    flex: none;
    width: ${P}px;
    height: ${P}px;
  }
  .ring {
    position: absolute;
    inset: 0;
    width: 100%;
    height: 100%;
  }
  .track,
  .progress {
    fill: none;
    stroke-width: ${ct};
  }
  .track {
    stroke: var(--divider-color, #e0e0e0);
  }
  .progress {
    stroke: var(--state-active-color, var(--primary-color));
  }
  .centre {
    position: absolute;
    inset: 0;
    display: flex;
    align-items: center;
    justify-content: center;
  }
  .time {
    color: var(--primary-text-color);
    font-size: var(--ha-font-size-l, 16px);
    font-weight: var(--ha-font-weight-medium, 500);
    font-variant-numeric: tabular-nums;
  }
  .round .icon {
    display: flex;
    --mdc-icon-size: 32px;
  }
  .round .text {
    position: relative;
    display: flex;
    flex-direction: column;
    align-items: center;
    max-width: 100%;
    min-width: 0;
  }
  .round .name {
    max-width: 100%;
  }
  /* For assistive technology only: what the ring and the icon say. */
  .round .status {
    position: absolute;
    width: 1px;
    height: 1px;
    overflow: hidden;
    clip-path: inset(50%);
    white-space: nowrap;
  }
  /*
   * While letting go would act, the ring pulses. A timer that is unavailable has nothing to
   * act on, so its ring stays still.
   */
  @keyframes pulse {
    from {
      opacity: 1;
      transform: scale(1);
    }
    to {
      opacity: 0.6;
      transform: scale(1.08);
    }
  }
  :host([data-held]) .round:not(.unavailable) .ring {
    animation: pulse 0.8s ease-in-out infinite alternate;
  }
  @media (prefers-reduced-motion: reduce) {
    :host([data-held]) .round:not(.unavailable) .ring {
      animation: none;
      transform: scale(1.08);
    }
  }
`;var fe="timerify-card",Bt={pill:{columns:6,rows:1,min_columns:3,min_rows:1,max_rows:1},round:{columns:3,rows:2,min_columns:2,min_rows:2,max_rows:3}},ye=class extends _{static properties={hass:{attribute:!1,noAccessor:!0},_config:{state:!0},_lookup:{state:!0}};static styles=[tt,at,ut,g`
      :host {
        display: block;
      }
      .warning {
        display: flex;
        align-items: center;
        gap: 12px;
        padding: 16px;
        color: var(--warning-color);
      }
    `];#e;#n=new Set;#i=!1;#t=!1;#o=new L(this,{tap:()=>this.#h?.open()}).binding();#d=new L(this,{tap:()=>this.#h?.open(),hold:()=>this.#m()}).binding();#s=()=>{let{_config:e,hass:t}=this;e?.chip!==void 0&&t!==void 0&&De(t,e.entity,e.chip)};#a;constructor(){super(),this._lookup={status:"pending"},new F(this,()=>this.#a?.endsAt)}get hass(){return this.#e}set hass(e){let t=this.#e;this.#e=e,this.requestUpdate("hass",t),this.#l(t,e)}setConfig(e){let t=qe(e),n=this._config?.entity!==t.entity;this._config=t,n&&(this._lookup={status:"pending"},this.#c())}getCardSize(){return this._config?.layout==="round"?3:1}getGridOptions(){return Bt[this._config?.layout??"pill"]}async getUpdateComplete(){let e=await super.getUpdateComplete();for(;this.#n.size>0;)await Promise.allSettled([...this.#n]),e=await super.getUpdateComplete();return e}#l(e,t){let n=e!==void 0&&t.connected&&!e.connected;(e===void 0||e.language!==t.language||n)&&this.#r(je(t));let o=this._config?.entity;o!==void 0&&(e===void 0||e.entities!==t.entities||n||E(t.states[o])&&!E(e.states[o]))&&this.#c()}#r(e){let t=e.finally(()=>this.#n.delete(t));this.#n.add(t)}#c(){if(this.#i){this.#t=!0;return}this.#i=!0,this.#r(this.#u())}async#u(){try{do{this.#t=!1;let e=this._config?.entity;if(this.#e===void 0||e===void 0)return;let t=await Qe(this.#e,e);this.#t||(this._lookup=t)}while(this.#t)}finally{this.#i=!1}}shouldUpdate(e){let t=this._lookup.status==="found"?this._lookup.info:void 0,n=this._config?q(this._config.entity,t):[];return G(e,this.#e,n)}get#h(){return this.renderRoot.querySelector("timerify-card-popup")}#m(){let{_config:e,hass:t}=this,n=this.#a?.state;e===void 0||t===void 0||(n==="counting"||n==="open"?Ue(t,e.entity,0):n==="idle"&&Ne(t,e.entity))}#p(e,t){if(this._lookup.status!=="not_found")return;let n=e.states[t.entity];return n===void 0?p(e,"card_entity_not_found",{entity:t.entity}):E(n)?p(e,"card_not_a_timer",{entity:t.entity}):void 0}render(){let e=this.#e,t=this._config;if(!e||!t)return l;let n=this.#p(e,t);if(n)return this.#a=void 0,m`
        <ha-card>
          <div class="warning" role="alert">
            <ha-icon icon="mdi:alert-outline"></ha-icon>
            <span>${n}</span>
          </div>
        </ha-card>
      `;let o=Date.now(),s=et(e,t,this._lookup,o);return this.#a=s,m`
      ${t.layout==="round"?ht(s,t,e,this.#d,o):rt(s,t,e,this.#o,this.#s,o)}
      ${this._lookup.status==="found"?m`
            <timerify-card-popup
              .hass=${e}
              .config=${t}
              .info=${this._lookup.info}
              .view=${s}
              @closed=${()=>this.renderRoot.querySelector(".body")?.focus()}
            ></timerify-card-popup>
          `:l}
    `}};if(!customElements.get(fe)){customElements.define("timerify-card-popup",X),customElements.define(fe,ye);let i={type:fe,name:"Timerify",description:p(void 0,"card_picker_description"),preview:!0,documentationURL:"https://github.com/klimofey/timerify#dashboard-card"};(window.customCards??=[]).push(i),Fe(()=>{i.description=p(j(),"card_picker_description")})}export{ye as TimerifyCard};
/*! Bundled license information:

@lit/reactive-element/css-tag.js:
  (**
   * @license
   * Copyright 2019 Google LLC
   * SPDX-License-Identifier: BSD-3-Clause
   *)

@lit/reactive-element/reactive-element.js:
lit-html/lit-html.js:
lit-element/lit-element.js:
lit-html/directive.js:
  (**
   * @license
   * Copyright 2017 Google LLC
   * SPDX-License-Identifier: BSD-3-Clause
   *)

lit-html/is-server.js:
  (**
   * @license
   * Copyright 2022 Google LLC
   * SPDX-License-Identifier: BSD-3-Clause
   *)

lit-html/directives/style-map.js:
  (**
   * @license
   * Copyright 2018 Google LLC
   * SPDX-License-Identifier: BSD-3-Clause
   *)
*/
