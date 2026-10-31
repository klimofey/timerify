var K=globalThis,q=K.ShadowRoot&&(K.ShadyCSS===void 0||K.ShadyCSS.nativeShadow)&&"adoptedStyleSheets"in Document.prototype&&"replace"in CSSStyleSheet.prototype,oe=Symbol(),we=new WeakMap,M=class{constructor(e,t,n){if(this._$cssResult$=!0,n!==oe)throw Error("CSSResult is not constructable. Use `unsafeCSS` or `css` instead.");this.cssText=e,this.t=t}get styleSheet(){let e=this.o,t=this.t;if(q&&e===void 0){let n=t!==void 0&&t.length===1;n&&(e=we.get(t)),e===void 0&&((this.o=e=new CSSStyleSheet).replaceSync(this.cssText),n&&we.set(t,e))}return e}toString(){return this.cssText}},$e=i=>new M(typeof i=="string"?i:i+"",void 0,oe),y=(i,...e)=>{let t=i.length===1?i[0]:e.reduce((n,o,s)=>n+(r=>{if(r._$cssResult$===!0)return r.cssText;if(typeof r=="number")return r;throw Error("Value passed to 'css' function must be a 'css' function result: "+r+". Use 'unsafeCSS' to pass non-literal values, but take care to ensure page security.")})(o)+i[s+1],i[0]);return new M(t,i,oe)},xe=(i,e)=>{if(q)i.adoptedStyleSheets=e.map(t=>t instanceof CSSStyleSheet?t:t.styleSheet);else for(let t of e){let n=document.createElement("style"),o=K.litNonce;o!==void 0&&n.setAttribute("nonce",o),n.textContent=t.cssText,i.appendChild(n)}},se=q?i=>i:i=>i instanceof CSSStyleSheet?(e=>{let t="";for(let n of e.cssRules)t+=n.cssText;return $e(t)})(i):i;var{is:yt,defineProperty:_t,getOwnPropertyDescriptor:vt,getOwnPropertyNames:bt,getOwnPropertySymbols:wt,getPrototypeOf:$t}=Object,G=globalThis,Ae=G.trustedTypes,xt=Ae?Ae.emptyScript:"",At=G.reactiveElementPolyfillSupport,O=(i,e)=>i,re={toAttribute(i,e){switch(e){case Boolean:i=i?xt:null;break;case Object:case Array:i=i==null?i:JSON.stringify(i)}return i},fromAttribute(i,e){let t=i;switch(e){case Boolean:t=i!==null;break;case Number:t=i===null?null:Number(i);break;case Object:case Array:try{t=JSON.parse(i)}catch{t=null}}return t}},Te=(i,e)=>!yt(i,e),ke={attribute:!0,type:String,converter:re,reflect:!1,useDefault:!1,hasChanged:Te};Symbol.metadata??=Symbol("metadata"),G.litPropertyMetadata??=new WeakMap;var v=class extends HTMLElement{static addInitializer(e){this._$Ei(),(this.l??=[]).push(e)}static get observedAttributes(){return this.finalize(),this._$Eh&&[...this._$Eh.keys()]}static createProperty(e,t=ke){if(t.state&&(t.attribute=!1),this._$Ei(),this.prototype.hasOwnProperty(e)&&((t=Object.create(t)).wrapped=!0),this.elementProperties.set(e,t),!t.noAccessor){let n=Symbol(),o=this.getPropertyDescriptor(e,n,t);o!==void 0&&_t(this.prototype,e,o)}}static getPropertyDescriptor(e,t,n){let{get:o,set:s}=vt(this.prototype,e)??{get(){return this[t]},set(r){this[t]=r}};return{get:o,set(r){let d=o?.call(this);s?.call(this,r),this.requestUpdate(e,d,n)},configurable:!0,enumerable:!0}}static getPropertyOptions(e){return this.elementProperties.get(e)??ke}static _$Ei(){if(this.hasOwnProperty(O("elementProperties")))return;let e=$t(this);e.finalize(),e.l!==void 0&&(this.l=[...e.l]),this.elementProperties=new Map(e.elementProperties)}static finalize(){if(this.hasOwnProperty(O("finalized")))return;if(this.finalized=!0,this._$Ei(),this.hasOwnProperty(O("properties"))){let t=this.properties,n=[...bt(t),...wt(t)];for(let o of n)this.createProperty(o,t[o])}let e=this[Symbol.metadata];if(e!==null){let t=litPropertyMetadata.get(e);if(t!==void 0)for(let[n,o]of t)this.elementProperties.set(n,o)}this._$Eh=new Map;for(let[t,n]of this.elementProperties){let o=this._$Eu(t,n);o!==void 0&&this._$Eh.set(o,t)}this.elementStyles=this.finalizeStyles(this.styles)}static finalizeStyles(e){let t=[];if(Array.isArray(e)){let n=new Set(e.flat(1/0).reverse());for(let o of n)t.unshift(se(o))}else e!==void 0&&t.push(se(e));return t}static _$Eu(e,t){let n=t.attribute;return n===!1?void 0:typeof n=="string"?n:typeof e=="string"?e.toLowerCase():void 0}constructor(){super(),this._$Ep=void 0,this.isUpdatePending=!1,this.hasUpdated=!1,this._$Em=null,this._$Ev()}_$Ev(){this._$ES=new Promise(e=>this.enableUpdating=e),this._$AL=new Map,this._$E_(),this.requestUpdate(),this.constructor.l?.forEach(e=>e(this))}addController(e){(this._$EO??=new Set).add(e),this.renderRoot!==void 0&&this.isConnected&&e.hostConnected?.()}removeController(e){this._$EO?.delete(e)}_$E_(){let e=new Map,t=this.constructor.elementProperties;for(let n of t.keys())this.hasOwnProperty(n)&&(e.set(n,this[n]),delete this[n]);e.size>0&&(this._$Ep=e)}createRenderRoot(){let e=this.shadowRoot??this.attachShadow(this.constructor.shadowRootOptions);return xe(e,this.constructor.elementStyles),e}connectedCallback(){this.renderRoot??=this.createRenderRoot(),this.enableUpdating(!0),this._$EO?.forEach(e=>e.hostConnected?.())}enableUpdating(e){}disconnectedCallback(){this._$EO?.forEach(e=>e.hostDisconnected?.())}attributeChangedCallback(e,t,n){this._$AK(e,n)}_$ET(e,t){let n=this.constructor.elementProperties.get(e),o=this.constructor._$Eu(e,n);if(o!==void 0&&n.reflect===!0){let s=(n.converter?.toAttribute!==void 0?n.converter:re).toAttribute(t,n.type);this._$Em=e,s==null?this.removeAttribute(o):this.setAttribute(o,s),this._$Em=null}}_$AK(e,t){let n=this.constructor,o=n._$Eh.get(e);if(o!==void 0&&this._$Em!==o){let s=n.getPropertyOptions(o),r=typeof s.converter=="function"?{fromAttribute:s.converter}:s.converter?.fromAttribute!==void 0?s.converter:re;this._$Em=o;let d=r.fromAttribute(t,s.type);this[o]=d??this._$Ej?.get(o)??d,this._$Em=null}}requestUpdate(e,t,n,o=!1,s){if(e!==void 0){let r=this.constructor;if(o===!1&&(s=this[e]),n??=r.getPropertyOptions(e),!((n.hasChanged??Te)(s,t)||n.useDefault&&n.reflect&&s===this._$Ej?.get(e)&&!this.hasAttribute(r._$Eu(e,n))))return;this.C(e,t,n)}this.isUpdatePending===!1&&(this._$ES=this._$EP())}C(e,t,{useDefault:n,reflect:o,wrapped:s},r){n&&!(this._$Ej??=new Map).has(e)&&(this._$Ej.set(e,r??t??this[e]),s!==!0||r!==void 0)||(this._$AL.has(e)||(this.hasUpdated||n||(t=void 0),this._$AL.set(e,t)),o===!0&&this._$Em!==e&&(this._$Eq??=new Set).add(e))}async _$EP(){this.isUpdatePending=!0;try{await this._$ES}catch(t){Promise.reject(t)}let e=this.scheduleUpdate();return e!=null&&await e,!this.isUpdatePending}scheduleUpdate(){return this.performUpdate()}performUpdate(){if(!this.isUpdatePending)return;if(!this.hasUpdated){if(this.renderRoot??=this.createRenderRoot(),this._$Ep){for(let[o,s]of this._$Ep)this[o]=s;this._$Ep=void 0}let n=this.constructor.elementProperties;if(n.size>0)for(let[o,s]of n){let{wrapped:r}=s,d=this[o];r!==!0||this._$AL.has(o)||d===void 0||this.C(o,void 0,s,d)}}let e=!1,t=this._$AL;try{e=this.shouldUpdate(t),e?(this.willUpdate(t),this._$EO?.forEach(n=>n.hostUpdate?.()),this.update(t)):this._$EM()}catch(n){throw e=!1,this._$EM(),n}e&&this._$AE(t)}willUpdate(e){}_$AE(e){this._$EO?.forEach(t=>t.hostUpdated?.()),this.hasUpdated||(this.hasUpdated=!0,this.firstUpdated(e)),this.updated(e)}_$EM(){this._$AL=new Map,this.isUpdatePending=!1}get updateComplete(){return this.getUpdateComplete()}getUpdateComplete(){return this._$ES}shouldUpdate(e){return!0}update(e){this._$Eq&&=this._$Eq.forEach(t=>this._$ET(t,this[t])),this._$EM()}updated(e){}firstUpdated(e){}};v.elementStyles=[],v.shadowRootOptions={mode:"open"},v[O("elementProperties")]=new Map,v[O("finalized")]=new Map,At?.({ReactiveElement:v}),(G.reactiveElementVersions??=[]).push("2.1.2");var me=globalThis,Ee=i=>i,Y=me.trustedTypes,Ce=Y?Y.createPolicy("lit-html",{createHTML:i=>i}):void 0,Oe="$lit$",w=`lit$${Math.random().toFixed(9).slice(2)}$`,De="?"+w,kt=`<${De}>`,k=document,U=()=>k.createComment(""),N=i=>i===null||typeof i!="object"&&typeof i!="function",pe=Array.isArray,Tt=i=>pe(i)||typeof i?.[Symbol.iterator]=="function",ae=`[ 	
\f\r]`,D=/<(?:(!--|\/[^a-zA-Z])|(\/?[a-zA-Z][^>\s]*)|(\/?$))/g,Se=/-->/g,Pe=/>/g,x=RegExp(`>|${ae}(?:([^\\s"'>=/]+)(${ae}*=${ae}*(?:[^ 	
\f\r"'\`<>=]|("|')|))|$)`,"g"),He=/'/g,Re=/"/g,Ue=/^(?:script|style|textarea|title)$/i,fe=i=>(e,...t)=>({_$litType$:i,strings:e,values:t}),h=fe(1),tn=fe(2),nn=fe(3),b=Symbol.for("lit-noChange"),l=Symbol.for("lit-nothing"),Me=new WeakMap,A=k.createTreeWalker(k,129);function Ne(i,e){if(!pe(i)||!i.hasOwnProperty("raw"))throw Error("invalid template strings array");return Ce!==void 0?Ce.createHTML(e):e}var Et=(i,e)=>{let t=i.length-1,n=[],o,s=e===2?"<svg>":e===3?"<math>":"",r=D;for(let d=0;d<t;d++){let a=i[d],u,m,c=-1,f=0;for(;f<a.length&&(r.lastIndex=f,m=r.exec(a),m!==null);)f=r.lastIndex,r===D?m[1]==="!--"?r=Se:m[1]!==void 0?r=Pe:m[2]!==void 0?(Ue.test(m[2])&&(o=RegExp("</"+m[2],"g")),r=x):m[3]!==void 0&&(r=x):r===x?m[0]===">"?(r=o??D,c=-1):m[1]===void 0?c=-2:(c=r.lastIndex-m[2].length,u=m[1],r=m[3]===void 0?x:m[3]==='"'?Re:He):r===Re||r===He?r=x:r===Se||r===Pe?r=D:(r=x,o=void 0);let g=r===x&&i[d+1].startsWith("/>")?" ":"";s+=r===D?a+kt:c>=0?(n.push(u),a.slice(0,c)+Oe+a.slice(c)+w+g):a+w+(c===-2?d:g)}return[Ne(i,s+(i[t]||"<?>")+(e===2?"</svg>":e===3?"</math>":"")),n]},I=class i{constructor({strings:e,_$litType$:t},n){let o;this.parts=[];let s=0,r=0,d=e.length-1,a=this.parts,[u,m]=Et(e,t);if(this.el=i.createElement(u,n),A.currentNode=this.el.content,t===2||t===3){let c=this.el.content.firstChild;c.replaceWith(...c.childNodes)}for(;(o=A.nextNode())!==null&&a.length<d;){if(o.nodeType===1){if(o.hasAttributes())for(let c of o.getAttributeNames())if(c.endsWith(Oe)){let f=m[r++],g=o.getAttribute(c).split(w),$=/([.?@])?(.*)/.exec(f);a.push({type:1,index:s,name:$[2],strings:g,ctor:$[1]==="."?ce:$[1]==="?"?le:$[1]==="@"?he:S}),o.removeAttribute(c)}else c.startsWith(w)&&(a.push({type:6,index:s}),o.removeAttribute(c));if(Ue.test(o.tagName)){let c=o.textContent.split(w),f=c.length-1;if(f>0){o.textContent=Y?Y.emptyScript:"";for(let g=0;g<f;g++)o.append(c[g],U()),A.nextNode(),a.push({type:2,index:++s});o.append(c[f],U())}}}else if(o.nodeType===8)if(o.data===De)a.push({type:2,index:s});else{let c=-1;for(;(c=o.data.indexOf(w,c+1))!==-1;)a.push({type:7,index:s}),c+=w.length-1}s++}}static createElement(e,t){let n=k.createElement("template");return n.innerHTML=e,n}};function C(i,e,t=i,n){if(e===b)return e;let o=n!==void 0?t._$Co?.[n]:t._$Cl,s=N(e)?void 0:e._$litDirective$;return o?.constructor!==s&&(o?._$AO?.(!1),s===void 0?o=void 0:(o=new s(i),o._$AT(i,t,n)),n!==void 0?(t._$Co??=[])[n]=o:t._$Cl=o),o!==void 0&&(e=C(i,o._$AS(i,e.values),o,n)),e}var de=class{constructor(e,t){this._$AV=[],this._$AN=void 0,this._$AD=e,this._$AM=t}get parentNode(){return this._$AM.parentNode}get _$AU(){return this._$AM._$AU}u(e){let{el:{content:t},parts:n}=this._$AD,o=(e?.creationScope??k).importNode(t,!0);A.currentNode=o;let s=A.nextNode(),r=0,d=0,a=n[0];for(;a!==void 0;){if(r===a.index){let u;a.type===2?u=new L(s,s.nextSibling,this,e):a.type===1?u=new a.ctor(s,a.name,a.strings,this,e):a.type===6&&(u=new ue(s,this,e)),this._$AV.push(u),a=n[++d]}r!==a?.index&&(s=A.nextNode(),r++)}return A.currentNode=k,o}p(e){let t=0;for(let n of this._$AV)n!==void 0&&(n.strings!==void 0?(n._$AI(e,n,t),t+=n.strings.length-2):n._$AI(e[t])),t++}},L=class i{get _$AU(){return this._$AM?._$AU??this._$Cv}constructor(e,t,n,o){this.type=2,this._$AH=l,this._$AN=void 0,this._$AA=e,this._$AB=t,this._$AM=n,this.options=o,this._$Cv=o?.isConnected??!0}get parentNode(){let e=this._$AA.parentNode,t=this._$AM;return t!==void 0&&e?.nodeType===11&&(e=t.parentNode),e}get startNode(){return this._$AA}get endNode(){return this._$AB}_$AI(e,t=this){e=C(this,e,t),N(e)?e===l||e==null||e===""?(this._$AH!==l&&this._$AR(),this._$AH=l):e!==this._$AH&&e!==b&&this._(e):e._$litType$!==void 0?this.$(e):e.nodeType!==void 0?this.T(e):Tt(e)?this.k(e):this._(e)}O(e){return this._$AA.parentNode.insertBefore(e,this._$AB)}T(e){this._$AH!==e&&(this._$AR(),this._$AH=this.O(e))}_(e){this._$AH!==l&&N(this._$AH)?this._$AA.nextSibling.data=e:this.T(k.createTextNode(e)),this._$AH=e}$(e){let{values:t,_$litType$:n}=e,o=typeof n=="number"?this._$AC(e):(n.el===void 0&&(n.el=I.createElement(Ne(n.h,n.h[0]),this.options)),n);if(this._$AH?._$AD===o)this._$AH.p(t);else{let s=new de(o,this),r=s.u(this.options);s.p(t),this.T(r),this._$AH=s}}_$AC(e){let t=Me.get(e.strings);return t===void 0&&Me.set(e.strings,t=new I(e)),t}k(e){pe(this._$AH)||(this._$AH=[],this._$AR());let t=this._$AH,n,o=0;for(let s of e)o===t.length?t.push(n=new i(this.O(U()),this.O(U()),this,this.options)):n=t[o],n._$AI(s),o++;o<t.length&&(this._$AR(n&&n._$AB.nextSibling,o),t.length=o)}_$AR(e=this._$AA.nextSibling,t){for(this._$AP?.(!1,!0,t);e!==this._$AB;){let n=Ee(e).nextSibling;Ee(e).remove(),e=n}}setConnected(e){this._$AM===void 0&&(this._$Cv=e,this._$AP?.(e))}},S=class{get tagName(){return this.element.tagName}get _$AU(){return this._$AM._$AU}constructor(e,t,n,o,s){this.type=1,this._$AH=l,this._$AN=void 0,this.element=e,this.name=t,this._$AM=o,this.options=s,n.length>2||n[0]!==""||n[1]!==""?(this._$AH=Array(n.length-1).fill(new String),this.strings=n):this._$AH=l}_$AI(e,t=this,n,o){let s=this.strings,r=!1;if(s===void 0)e=C(this,e,t,0),r=!N(e)||e!==this._$AH&&e!==b,r&&(this._$AH=e);else{let d=e,a,u;for(e=s[0],a=0;a<s.length-1;a++)u=C(this,d[n+a],t,a),u===b&&(u=this._$AH[a]),r||=!N(u)||u!==this._$AH[a],u===l?e=l:e!==l&&(e+=(u??"")+s[a+1]),this._$AH[a]=u}r&&!o&&this.j(e)}j(e){e===l?this.element.removeAttribute(this.name):this.element.setAttribute(this.name,e??"")}},ce=class extends S{constructor(){super(...arguments),this.type=3}j(e){this.element[this.name]=e===l?void 0:e}},le=class extends S{constructor(){super(...arguments),this.type=4}j(e){this.element.toggleAttribute(this.name,!!e&&e!==l)}},he=class extends S{constructor(e,t,n,o,s){super(e,t,n,o,s),this.type=5}_$AI(e,t=this){if((e=C(this,e,t,0)??l)===b)return;let n=this._$AH,o=e===l&&n!==l||e.capture!==n.capture||e.once!==n.once||e.passive!==n.passive,s=e!==l&&(n===l||o);o&&this.element.removeEventListener(this.name,this,n),s&&this.element.addEventListener(this.name,this,e),this._$AH=e}handleEvent(e){typeof this._$AH=="function"?this._$AH.call(this.options?.host??this.element,e):this._$AH.handleEvent(e)}},ue=class{constructor(e,t,n){this.element=e,this.type=6,this._$AN=void 0,this._$AM=t,this.options=n}get _$AU(){return this._$AM._$AU}_$AI(e){C(this,e)}};var Ct=me.litHtmlPolyfillSupport;Ct?.(I,L),(me.litHtmlVersions??=[]).push("3.3.3");var Ie=(i,e,t)=>{let n=t?.renderBefore??e,o=n._$litPart$;if(o===void 0){let s=t?.renderBefore??null;n._$litPart$=o=new L(e.insertBefore(U(),s),s,void 0,t??{})}return o._$AI(i),o};var ge=globalThis,_=class extends v{constructor(){super(...arguments),this.renderOptions={host:this},this._$Do=void 0}createRenderRoot(){let e=super.createRenderRoot();return this.renderOptions.renderBefore??=e.firstChild,e}update(e){let t=this.render();this.hasUpdated||(this.renderOptions.isConnected=this.isConnected),super.update(e),this._$Do=Ie(t,this.renderRoot,this.renderOptions)}connectedCallback(){super.connectedCallback(),this._$Do?.setConnected(!0)}disconnectedCallback(){super.disconnectedCallback(),this._$Do?.setConnected(!1)}render(){return b}};_._$litElement$=!0,_.finalized=!0,ge.litElementHydrateSupport?.({LitElement:_});var St=ge.litElementPolyfillSupport;St?.({LitElement:_});(ge.litElementVersions??=[]).push("4.2.2");async function z(i,e,t,n,o){try{await i.callService(e,t,n,{entity_id:o})}catch{}}function V(i,e,t){return z(i,"number","set_value",{value:t},e)}function W(i,e,t){return z(i,"timerify","add_time",{minutes:t},e)}function Le(i,e){return z(i,"timerify","run",{},e)}function ze(i,e,t){return z(i,"switch",t?"turn_on":"turn_off",{},e)}function Ve(i,e,t){return z(i,"timerify","cancel_command",{command_id:t},e)}var We={card_entity_not_found:"Entity not found: {entity}",card_not_a_timer:"{entity} is not the Run for number of a Timerify timer",card_error_entity:"Choose the Run for number of a timer",card_error_layout:"The layout is pill or round",card_error_presets:"Presets are whole minutes from 1 to 1440",card_error_chip:"The quick chip is whole minutes from 1 to 1440",card_close:"Close",card_until:"until {time}",card_add_time:"Add {duration}",card_subtract_time:"Take off {duration}",card_stop:"Stop",card_schedule:"Schedule",card_commands:"Pending commands",card_command_on:"On at {time}",card_command_on_for:"On at {time} for {duration}",card_command_off:"Off at {time}",card_cancel_command:"Cancel",card_settings:"Settings",card_picker_description:"The countdown, presets and schedule of a Timerify timer"};var Be="common",Fe="timerify",Ht=`component.${Fe}.${Be}.`;function Rt(i,e){return i.replace(/\{(\w+)\}/g,(t,n)=>String(e?.[n]??t))}function p(i,e,t){return i?.localize(Ht+e,t)||Rt(We[e],t)}var j,je=Promise.resolve(),Ke,qe=new Set;function Ge(i){return i.language!==j&&(j=i.language,je=Mt(i,i.language)),je}async function Mt(i,e){let t;try{t=await i.loadBackendTranslation(Be,Fe)}catch{j===e&&(j=void 0);return}j===e&&(Ke={...i,localize:t},qe.forEach(n=>n()))}function X(){return Ke}function Ye(i){qe.add(i)}var Ot=[15,30,45,60,120],Dt=1440,T=class extends Error{constructor(t){super(p(X(),t));this.key=t}key};function Xe(i){let e=typeof i=="number"?i:typeof i=="string"&&/^\d+$/.test(i)?Number(i):void 0;return e!==void 0&&Number.isInteger(e)&&e>=1&&e<=Dt?e:void 0}function Ut(i){if(i===void 0)return[...Ot];if(!Array.isArray(i)||i.length===0)throw new T("card_error_presets");let e=new Set;for(let t of i){let n=Xe(t);if(n===void 0)throw new T("card_error_presets");e.add(n)}return[...e]}function Nt(i){if(i===void 0)return;let e=Xe(i);if(e===void 0)throw new T("card_error_chip");return e}function Ze(i){let e=typeof i=="object"&&i!==null?i:{},{entity:t,layout:n="pill",name:o,icon:s}=e;if(typeof t!="string"||!/^number\.[a-z0-9_]+$/.test(t))throw new T("card_error_entity");if(n!=="pill"&&n!=="round")throw new T("card_error_layout");let r=Nt(e.chip);return{entity:t,layout:n,...typeof o=="string"&&o!==""&&{name:o},...typeof s=="string"&&s!==""&&{icon:s},presets:Ut(e.presets),...r!==void 0&&{chip:r}}}var Z=class{#e;#i;#t=!1;#n;constructor(e,t){this.#e=e,this.#i=t,e.addController(this)}hostConnected(){this.#t=!0,this.#o()}hostUpdated(){this.#o()}hostDisconnected(){this.#t=!1,this.#o()}#o(){let e=this.#i(),t=this.#t&&e!==void 0&&e.getTime()>Date.now();t&&this.#n===void 0?this.#n=setInterval(()=>this.#e.requestUpdate(),1e3):!t&&this.#n!==void 0&&(clearInterval(this.#n),this.#n=void 0)}};var Je=i=>String(i).padStart(2,"0");function P(i){let e=Math.ceil(Math.max(0,i)),t=Math.floor(e/3600),n=Math.floor(e%3600/60),o=Je(e%60);return t>0?`${t}:${Je(n)}:${o}`:`${n}:${o}`}function It({language:i,time_format:e}){if(e==="12"||e==="24")return e==="12";let t=new Intl.DateTimeFormat(e==="language"?i:void 0,{hour:"numeric"}).resolvedOptions();return t.hourCycle==="h11"||t.hourCycle==="h12"}var Lt=864e5;function Qe(i,e){let t=new Intl.DateTimeFormat("en-US",{timeZone:i,year:"numeric",month:"numeric",day:"numeric"}).formatToParts(e),n=o=>Number(t.find(s=>s.type===o)?.value);return Date.UTC(n("year"),n("month")-1,n("day"))/Lt}function B(i,e,t){let{locale:n}=i,o=n.time_zone==="server"?i.config.time_zone:void 0,s=Qe(o,e.getTime())-Qe(o,t),r=s===0?{}:s>=1&&s<=6?{weekday:"short"}:{month:"short",day:"numeric"};return new Intl.DateTimeFormat(n.language,{...r,hour:"numeric",minute:"2-digit",hourCycle:It(n)?"h12":"h23",timeZone:o}).format(e)}function E(i,e){let t=(r,d)=>new Intl.NumberFormat(i.locale.language,{style:"unit",unit:d,unitDisplay:"short",useGrouping:!1}).format(r),n=Math.floor(e/60),o=e%60,s=n>0?[t(n,"hour")]:[];return(o>0||n===0)&&s.push(t(o,"minute")),s.join(" ")}var zt=new Set(["brightness_pct","percentage","humidity"]);function et(i,e,t,n){return zt.has(t)&&typeof n=="number"?new Intl.NumberFormat(i.locale.language,{style:"percent",maximumFractionDigits:1}).format(n/100):e===void 0?String(n):t==="hvac_mode"?i.formatEntityState(e,String(n)):i.formatEntityAttributeValue(e,t,n)}var Vt="not_found";async function it(i,e){try{return{status:"found",info:await i.callWS({type:"timerify/timer",entity_id:e})}}catch(t){return{status:typeof t=="object"&&t!==null&&"code"in t&&t.code===Vt?"not_found":"failed"}}}var H=i=>i!==void 0&&i.state!=="unavailable"&&i.state!=="unknown";function Wt(i,e){return i===void 0||i.state==="unavailable"||i.state==="unknown"?!1:e.states.includes(i.state)===(e.match==="is")}var jt="mdi:timer-outline",tt=i=>i===void 0||i.state==="unavailable";function nt(i){let e=typeof i=="string"?Date.parse(i):Number.NaN;return Number.isNaN(e)?void 0:e}function ot(i,e,t,n){let o=t.status==="found"?t.info:void 0,s=i.states[e.entity],r=o&&i.states[o.target],d=e.name||r&&i.formatEntityName(r,void 0)||s?.attributes.friendly_name||e.entity,a=e.icon?{icon:e.icon}:r?{stateObj:r}:{icon:jt},u={name:d,icon:a,target:r,remaining:0},m=o&&i.states[o.ends_at];if(o===void 0||m===void 0||tt(s)||tt(m))return{...u,state:"unavailable",progress:0};let c=nt(m.state);if(c===void 0)return Wt(r,o.target_on)?{...u,state:"open",progress:1}:{...u,state:"idle",progress:0};let f=nt(m.attributes.started_at),g=f===void 0?0:(c-f)/1e3,$=Math.max(0,(c-n)/1e3);return{...u,state:"counting",remaining:$,progress:g>0?Math.min(1,$/g):1,endsAt:new Date(c)}}function J(i,e){return e?[i,e.ends_at,e.next_command,e.target,...e.intervals.map(({entity_id:t})=>t)]:[i]}var Bt=["locale","language","localize","config","user","connected","entities"];function Q(i,e,t){for(let o of i.keys())if(o!=="hass")return!0;let n=i.get("hass");return n===void 0||e===void 0?!0:Bt.some(o=>n[o]!==e[o])||t.some(o=>n.states[o]!==e.states[o])}function ee(i){return"stateObj"in i.icon?h`<ha-state-icon .stateObj=${i.icon.stateObj}></ha-state-icon>`:h`<ha-icon .icon=${i.icon.icon}></ha-icon>`}function Ft(i,e,t){if(i.state!=="unavailable")return i.target?t.formatEntityState(i.target):"";let n=t.states[e.entity];if(H(n))return"";let o={entity_id:e.entity,state:"unavailable",attributes:{}};return t.formatEntityState(n??o,"unavailable")}function te(i,e,t,n){if(i.state!=="counting"||i.endsAt===void 0)return Ft(i,e,t);let o=B(t,i.endsAt,n);return h`
    <span class="remaining">${P(i.remaining)}</span>
    <span class="until">${p(t,"card_until",{time:o})}</span>
  `}var st=y`
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
`;var rt={ATTRIBUTE:1,CHILD:2,PROPERTY:3,BOOLEAN_ATTRIBUTE:4,EVENT:5,ELEMENT:6},at=i=>(...e)=>({_$litDirective$:i,values:e}),ne=class{constructor(e){}get _$AU(){return this._$AM._$AU}_$AT(e,t,n){this._$Ct=e,this._$AM=t,this._$Ci=n}_$AS(e,t){return this.update(e,t)}update(e,t){return this.render(...t)}};var dt="important",Kt=" !"+dt,ct=at(class extends ne{constructor(i){if(super(i),i.type!==rt.ATTRIBUTE||i.name!=="style"||i.strings?.length>2)throw Error("The `styleMap` directive must be used in the `style` attribute and must be the only part in the attribute.")}render(i){return Object.keys(i).reduce((e,t)=>{let n=i[t];return n==null?e:e+`${t=t.includes("-")?t:t.replace(/(?:^(webkit|moz|ms|o)|)(?=[A-Z])/g,"-$&").toLowerCase()}:${n};`},"")}update(i,[e]){let{style:t}=i.element;if(this.ft===void 0)return this.ft=new Set(Object.keys(e)),this.render(e);for(let n of this.ft)e[n]==null&&(this.ft.delete(n),n.includes("-")?t.removeProperty(n):t[n]=null);for(let n in e){let o=e[n];if(o!=null){this.ft.add(n);let s=typeof o=="string"&&o.endsWith(Kt);n.includes("-")||s?t.setProperty(n,s?o.slice(0,-11):o,s?dt:""):t[n]=o}}return b}});function lt(i,e,t,n,o,s){let r=Math.round(i.progress*1e3)/10;return h`
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
          <span class="fill" style=${ct({width:`${r}%`})}></span>
        </span>
      </div>
      <div class="content">
        <span class="icon">${ee(i)}</span>
        <span class="text" id="label">
          <span class="name">${i.name}</span>
          <span class="status">${te(i,e,t,s)}</span>
        </span>
        ${e.chip===void 0?l:h`
              <button
                class="chip"
                type="button"
                aria-label=${p(t,"card_add_time",{duration:E(t,e.chip)})}
                @click=${o}
              >
                +${E(t,e.chip)}
              </button>
            `}
      </div>
    </ha-card>
  `}var ht=y`
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
`;function qt(i){let e=i?.attributes.commands;return Array.isArray(e)?e.flatMap(t=>{if(typeof t!="object"||t===null)return[];let{id:n,at:o,action:s,minutes:r,settings:d}=t,a=typeof o=="string"?new Date(o):void 0;return typeof n!="string"||a===void 0||Number.isNaN(a.getTime())||s!=="on"&&s!=="off"?[]:[{id:n,at:a,action:s,minutes:typeof r=="number"&&r>0?r:null,settings:typeof d=="object"&&d!==null?Object.entries(d):[]}]}):[]}var Gt=i=>`/config/integrations/integration/timerify#config_entry=${encodeURIComponent(i)}`,ie=class extends _{static properties={hass:{attribute:!1},config:{attribute:!1},info:{attribute:!1},view:{attribute:!1},opened:{state:!0}};static styles=y`
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
      display: flex;
      flex-direction: column;
      gap: 16px;
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
    h3 {
      margin: 0 0 4px;
      color: var(--secondary-text-color);
      font-size: var(--ha-font-size-m, 14px);
      font-weight: var(--ha-font-weight-medium, 500);
    }
    button,
    a {
      font: inherit;
      cursor: pointer;
    }
    button:focus-visible,
    a:focus-visible {
      outline: 2px solid var(--primary-color);
      outline-offset: 2px;
    }
    button.close {
      padding: 8px 12px;
      border: none;
      border-radius: var(--ha-border-radius-md, 8px);
      background: none;
      color: var(--primary-color);
    }
    .countdown {
      display: flex;
      flex-wrap: wrap;
      align-items: baseline;
      gap: 4px 12px;
      margin: 0;
    }
    .remaining {
      font-size: var(--ha-font-size-3xl, 2rem);
      font-variant-numeric: tabular-nums;
      font-weight: var(--ha-font-weight-medium, 500);
    }
    .until {
      color: var(--secondary-text-color);
    }
    .presets,
    .adjust {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }
    button.action {
      min-width: 40px;
      min-height: 40px;
      padding: 0 16px;
      border: none;
      border-radius: 20px;
      background: var(--secondary-background-color);
      color: var(--primary-text-color);
    }
    button.action:disabled {
      color: var(--disabled-text-color);
      cursor: default;
    }
    button.stop:not(:disabled) {
      color: var(--error-color);
    }
    ul {
      margin: 0;
      padding: 0;
      list-style: none;
    }
    li {
      display: flex;
      align-items: center;
      gap: 8px;
      min-height: 48px;
    }
    button.interval {
      display: flex;
      flex: 1 1 auto;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      min-height: 48px;
      padding: 0;
      border: none;
      background: none;
      color: var(--primary-text-color);
      text-align: start;
    }
    button.interval:disabled {
      color: var(--disabled-text-color);
      cursor: default;
    }
    .label {
      display: flex;
      flex-direction: column;
    }
    .state {
      color: var(--secondary-text-color);
      font-size: var(--ha-font-size-s, 12px);
    }
    .track {
      position: relative;
      flex: none;
      width: 40px;
      height: 22px;
      border-radius: 11px;
      background: var(--disabled-text-color);
      transition: background-color var(--ha-animation-duration-fast, 150ms);
    }
    .knob {
      position: absolute;
      top: 3px;
      inset-inline-start: 3px;
      width: 16px;
      height: 16px;
      border-radius: 50%;
      background: var(--card-background-color);
      transition: transform var(--ha-animation-duration-fast, 150ms);
    }
    [aria-checked="true"] .track {
      background: var(--primary-color);
    }
    [aria-checked="true"] .knob {
      transform: translateX(18px);
    }
    [aria-checked="true"]:dir(rtl) .knob {
      transform: translateX(-18px);
    }
    button.interval:disabled .track {
      opacity: 0.5;
    }
    .command {
      display: flex;
      flex: 1 1 auto;
      flex-direction: column;
      min-width: 0;
    }
    .settings {
      color: var(--secondary-text-color);
      font-size: var(--ha-font-size-s, 12px);
    }
    button.cancel {
      flex: none;
      width: 40px;
      height: 40px;
      border: none;
      border-radius: 50%;
      background: none;
      color: var(--secondary-text-color);
      font-size: var(--ha-font-size-xl, 1.25rem);
      line-height: 1;
    }
    button.cancel:disabled {
      color: var(--disabled-text-color);
      cursor: default;
    }
    footer {
      display: flex;
      justify-content: flex-end;
    }
    a {
      color: var(--primary-color);
    }
  `;constructor(){super(),this.opened=!1}open(){this.opened=!0}close(){this.#e?.close(),this.#r()}disconnectedCallback(){super.disconnectedCallback(),this.close()}get#e(){return this.renderRoot.querySelector("dialog")}#i=()=>{this.#e?.open||this.#r()};#t=!1;#n=e=>{this.#t=e.target===e.currentTarget};#o=e=>{this.#t&&=e.target===e.currentTarget};#d=()=>{this.#t=!1};#s=e=>{let t=this.#t&&e.target===e.currentTarget;this.#t=!1,t&&this.close()};#r(){this.opened&&(this.opened=!1,this.dispatchEvent(new CustomEvent("closed")))}shouldUpdate(e){if(!this.hasUpdated||e.has("opened"))return!0;let t=J(this.config.entity,this.info);return this.opened&&Q(e,this.hass,t)}updated(e){let t=this.#e;e.has("opened")&&this.opened&&t&&!t.open&&t.showModal()}render(){return h`
      <dialog
        aria-labelledby="title"
        @cancel=${()=>this.close()}
        @close=${this.#i}
        @pointerdown=${this.#n}
        @pointerup=${this.#o}
        @pointercancel=${this.#d}
        @click=${this.#s}
      >
        ${this.opened?this.#c():l}
      </dialog>
    `}#c(){let{hass:e,view:t}=this,n=Date.now();return h`
      <div class="wrapper">
        <header>
          <h2 id="title">${t.name}</h2>
          <button class="close" @click=${()=>this.close()}>${p(e,"card_close")}</button>
        </header>
        ${this.#a(n)} ${this.#l()} ${this.#u()} ${this.#m(n)}
        ${this.#f()}
      </div>
    `}#a(e){let{hass:t,view:n}=this;if(n.state!=="counting"||n.endsAt===void 0)return l;let o=B(t,n.endsAt,e);return h`
      <p class="countdown">
        <span class="remaining">${P(n.remaining)}</span>
        <span class="until">${p(t,"card_until",{time:o})}</span>
      </p>
    `}#l(){let{hass:e,config:t,view:n}=this,o=E(e,5),s=n.state==="counting",r=s||n.state==="open",d=n.state==="unavailable";return h`
      <div class="presets">
        ${t.presets.map(a=>h`
            <button
              class="action preset"
              ?disabled=${d}
              @click=${()=>{V(e,t.entity,a)}}
            >
              ${E(e,a)}
            </button>
          `)}
      </div>
      <div class="adjust">
        <button
          class="action step"
          aria-label=${p(e,"card_subtract_time",{duration:o})}
          ?disabled=${!s}
          @click=${()=>{W(e,t.entity,-5)}}
        >
          −${o}
        </button>
        <button
          class="action step"
          aria-label=${p(e,"card_add_time",{duration:o})}
          ?disabled=${d}
          @click=${()=>{W(e,t.entity,5)}}
        >
          +${o}
        </button>
        <button
          class="action stop"
          ?disabled=${!r}
          @click=${()=>{V(e,t.entity,0)}}
        >
          ${p(e,"card_stop")}
        </button>
      </div>
    `}#u(){let{intervals:e}=this.info;return e.length===0?l:h`
      <section class="schedule">
        <h3>${p(this.hass,"card_schedule")}</h3>
        <ul>
          ${e.map(t=>h`<li>${this.#h(t)}</li>`)}
        </ul>
      </section>
    `}#h({entity_id:e,title:t}){let{hass:n}=this,o=n.states[e],s=o!==void 0&&o.state!=="unavailable",r=s&&o.state==="on",d=o??{entity_id:e,state:"unavailable",attributes:{}};return h`
      <button
        class="interval"
        role="switch"
        aria-checked=${r?"true":"false"}
        ?disabled=${!s}
        @click=${()=>{ze(n,e,!r)}}
      >
        <span class="label">
          <span class="title">${t}</span>
          ${s?l:h`<span class="state">${n.formatEntityState(d,"unavailable")}</span>`}
        </span>
        <span class="track" aria-hidden="true"><span class="knob"></span></span>
      </button>
    `}#m(e){let{hass:t,config:n,info:o,view:s}=this,r=qt(t.states[o.next_command]);if(r.length===0)return l;let d=s.state==="unavailable";return h`
      <section class="commands">
        <h3>${p(t,"card_commands")}</h3>
        <ul>
          ${r.map((a,u)=>{let m=a.settings.map(([c,f])=>et(t,s.target,c,f));return h`
              <li>
                <div class="command" id="command-${u}">
                  <span class="what">${this.#p(a,e)}</span>
                  ${m.length===0?l:h`<span class="settings">${m.join(", ")}</span>`}
                </div>
                <button
                  class="cancel"
                  aria-label=${p(t,"card_cancel_command")}
                  aria-describedby="command-${u}"
                  ?disabled=${d}
                  @click=${()=>{Ve(t,n.entity,a.id)}}
                >
                  <span aria-hidden="true">×</span>
                </button>
              </li>
            `})}
        </ul>
      </section>
    `}#p(e,t){let{hass:n}=this,o=B(n,e.at,t);return e.action==="off"?p(n,"card_command_off",{time:o}):e.minutes===null?p(n,"card_command_on",{time:o}):p(n,"card_command_on_for",{time:o,duration:E(n,e.minutes)})}#f(){return this.hass.user?.is_admin?h`
      <footer>
        <a href=${Gt(this.info.entry_id)} @click=${this.#g}>
          ${p(this.hass,"card_settings")}
        </a>
      </footer>
    `:l}#g=e=>{!e.ctrlKey&&!e.metaKey&&!e.shiftKey&&this.close()}};var ut="data-held",F=class{#e;#i;#t=!1;#n;#o;#d=!1;#s=!1;constructor(e,t){this.#e=e,this.#i=t,e.addController(this)}hostDisconnected(){this.#t=!1,this.#s=!1,this.#a()}binding(){let e={click:n=>{if(this.#s){this.#s=!1,n.preventDefault(),n.stopPropagation();return}this.#i.tap()},keydown:n=>{n.key==="Enter"?(n.preventDefault(),n.repeat||this.#i.tap()):n.key===" "&&(n.preventDefault(),this.#t=!0)},keyup:n=>{if(n.key!==" ")return;let o=this.#t;this.#t=!1,o&&this.#i.tap()}},{hold:t}=this.#i;return t===void 0?e:{...e,pointerdown:n=>this.#r(n),pointerup:n=>{if(n.pointerId!==this.#n)return;let o=this.#d;this.#a(),o&&(this.#s=!0,t())},pointercancel:n=>this.#c(n),pointerleave:n=>this.#c(n),contextmenu:n=>{this.#n!==void 0&&n.preventDefault()}}}#r(e){!e.isPrimary||e.button!==0||(this.#s=!1,this.#a(),this.#n=e.pointerId,this.#o=setTimeout(()=>{this.#o=void 0,this.#d=!0,this.#e.setAttribute(ut,"")},500))}#c(e){e.pointerId===this.#n&&this.#a()}#a(){clearTimeout(this.#o),this.#o=void 0,this.#n=void 0,this.#d=!1,this.#e.removeAttribute(ut)}};var R=80,pt=6,_e=(R-pt)/2,mt=2*Math.PI*_e;function Yt(i){if(i.state!=="counting")return h`<span class="icon">${ee(i)}</span>`;let e=P(i.remaining);return h`<span class="time" aria-hidden="true">${e}</span>`}function ft(i,e,t,n,o){let s=R/2;return h`
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
          <svg class="ring" viewBox="0 0 ${R} ${R}" aria-hidden="true">
            <circle class="track" cx=${s} cy=${s} r=${_e}></circle>
            <circle
              class="progress"
              cx=${s}
              cy=${s}
              r=${_e}
              transform="rotate(-90 ${s} ${s})"
              stroke-dasharray=${mt}
              stroke-dashoffset=${(1-i.progress)*mt}
            ></circle>
          </svg>
          <span class="centre">
            ${Yt(i)}
          </span>
        </div>
        <span class="text" id="label">
          <span class="name">${i.name}</span>
          <span class="status">${te(i,e,t,o)}</span>
        </span>
      </div>
    </ha-card>
  `}var gt=y`
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
    width: ${R}px;
    height: ${R}px;
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
    stroke-width: ${pt};
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
`;var ve="timerify-card",Xt={pill:{columns:6,rows:1,min_columns:3,min_rows:1,max_rows:1},round:{columns:3,rows:2,min_columns:2,min_rows:2,max_rows:3}},be=class extends _{static properties={hass:{attribute:!1,noAccessor:!0},_config:{state:!0},_lookup:{state:!0}};static styles=[st,ht,gt,y`
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
    `];#e;#i=new Set;#t=!1;#n=!1;#o=new F(this,{tap:()=>this.#h?.open()}).binding();#d=new F(this,{tap:()=>this.#h?.open(),hold:()=>this.#m()}).binding();#s=()=>{let{_config:e,hass:t}=this;e?.chip!==void 0&&t!==void 0&&W(t,e.entity,e.chip)};#r;constructor(){super(),this._lookup={status:"pending"},new Z(this,()=>this.#r?.endsAt)}get hass(){return this.#e}set hass(e){let t=this.#e;this.#e=e,this.requestUpdate("hass",t),this.#c(t,e)}setConfig(e){let t=Ze(e),n=this._config?.entity!==t.entity;this._config=t,n&&(this._lookup={status:"pending"},this.#l())}getCardSize(){return this._config?.layout==="round"?3:1}getGridOptions(){return Xt[this._config?.layout??"pill"]}async getUpdateComplete(){let e=await super.getUpdateComplete();for(;this.#i.size>0;)await Promise.allSettled([...this.#i]),e=await super.getUpdateComplete();return e}#c(e,t){let n=e!==void 0&&t.connected&&!e.connected;(e===void 0||e.language!==t.language||n)&&this.#a(Ge(t));let o=this._config?.entity;o!==void 0&&(e===void 0||e.entities!==t.entities||n||H(t.states[o])&&!H(e.states[o]))&&this.#l()}#a(e){let t=e.finally(()=>this.#i.delete(t));this.#i.add(t)}#l(){if(this.#t){this.#n=!0;return}this.#t=!0,this.#a(this.#u())}async#u(){try{do{this.#n=!1;let e=this._config?.entity;if(this.#e===void 0||e===void 0)return;let t=await it(this.#e,e);this.#n||(this._lookup=t)}while(this.#n)}finally{this.#t=!1}}shouldUpdate(e){let t=this._lookup.status==="found"?this._lookup.info:void 0,n=this._config?J(this._config.entity,t):[];return Q(e,this.#e,n)}get#h(){return this.renderRoot.querySelector("timerify-card-popup")}#m(){let{_config:e,hass:t}=this,n=this.#r?.state;e===void 0||t===void 0||(n==="counting"||n==="open"?V(t,e.entity,0):n==="idle"&&Le(t,e.entity))}#p(e,t){if(this._lookup.status!=="not_found")return;let n=e.states[t.entity];return n===void 0?p(e,"card_entity_not_found",{entity:t.entity}):H(n)?p(e,"card_not_a_timer",{entity:t.entity}):void 0}render(){let e=this.#e,t=this._config;if(!e||!t)return l;let n=this.#p(e,t);if(n)return this.#r=void 0,h`
        <ha-card>
          <div class="warning" role="alert">
            <ha-icon icon="mdi:alert-outline"></ha-icon>
            <span>${n}</span>
          </div>
        </ha-card>
      `;let o=Date.now(),s=ot(e,t,this._lookup,o);return this.#r=s,h`
      ${t.layout==="round"?ft(s,t,e,this.#d,o):lt(s,t,e,this.#o,this.#s,o)}
      ${this._lookup.status==="found"?h`
            <timerify-card-popup
              .hass=${e}
              .config=${t}
              .info=${this._lookup.info}
              .view=${s}
              @closed=${()=>this.renderRoot.querySelector(".body")?.focus()}
            ></timerify-card-popup>
          `:l}
    `}};if(!customElements.get(ve)){customElements.define("timerify-card-popup",ie),customElements.define(ve,be);let i={type:ve,name:"Timerify",description:p(void 0,"card_picker_description"),preview:!0,documentationURL:"https://github.com/klimofey/timerify#dashboard-card"};(window.customCards??=[]).push(i),Ye(()=>{i.description=p(X(),"card_picker_description")})}export{be as TimerifyCard};
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
