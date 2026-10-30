var L=globalThis,D=L.ShadowRoot&&(L.ShadyCSS===void 0||L.ShadyCSS.nativeShadow)&&"adoptedStyleSheets"in Document.prototype&&"replace"in CSSStyleSheet.prototype,q=Symbol(),he=new WeakMap,C=class{constructor(e,t,n){if(this._$cssResult$=!0,n!==q)throw Error("CSSResult is not constructable. Use `unsafeCSS` or `css` instead.");this.cssText=e,this.t=t}get styleSheet(){let e=this.o,t=this.t;if(D&&e===void 0){let n=t!==void 0&&t.length===1;n&&(e=he.get(t)),e===void 0&&((this.o=e=new CSSStyleSheet).replaceSync(this.cssText),n&&he.set(t,e))}return e}toString(){return this.cssText}},ce=i=>new C(typeof i=="string"?i:i+"",void 0,q),x=(i,...e)=>{let t=i.length===1?i[0]:e.reduce((n,s,o)=>n+(r=>{if(r._$cssResult$===!0)return r.cssText;if(typeof r=="number")return r;throw Error("Value passed to 'css' function must be a 'css' function result: "+r+". Use 'unsafeCSS' to pass non-literal values, but take care to ensure page security.")})(s)+i[o+1],i[0]);return new C(t,i,q)},le=(i,e)=>{if(D)i.adoptedStyleSheets=e.map(t=>t instanceof CSSStyleSheet?t:t.styleSheet);else for(let t of e){let n=document.createElement("style"),s=L.litNonce;s!==void 0&&n.setAttribute("nonce",s),n.textContent=t.cssText,i.appendChild(n)}},F=D?i=>i:i=>i instanceof CSSStyleSheet?(e=>{let t="";for(let n of e.cssRules)t+=n.cssText;return ce(t)})(i):i;var{is:Ie,defineProperty:Ve,getOwnPropertyDescriptor:Be,getOwnPropertyNames:ze,getOwnPropertySymbols:je,getPrototypeOf:Ke}=Object,W=globalThis,ue=W.trustedTypes,qe=ue?ue.emptyScript:"",Fe=W.reactiveElementPolyfillSupport,P=(i,e)=>i,G={toAttribute(i,e){switch(e){case Boolean:i=i?qe:null;break;case Object:case Array:i=i==null?i:JSON.stringify(i)}return i},fromAttribute(i,e){let t=i;switch(e){case Boolean:t=i!==null;break;case Number:t=i===null?null:Number(i);break;case Object:case Array:try{t=JSON.parse(i)}catch{t=null}}return t}},pe=(i,e)=>!Ie(i,e),me={attribute:!0,type:String,converter:G,reflect:!1,useDefault:!1,hasChanged:pe};Symbol.metadata??=Symbol("metadata"),W.litPropertyMetadata??=new WeakMap;var g=class extends HTMLElement{static addInitializer(e){this._$Ei(),(this.l??=[]).push(e)}static get observedAttributes(){return this.finalize(),this._$Eh&&[...this._$Eh.keys()]}static createProperty(e,t=me){if(t.state&&(t.attribute=!1),this._$Ei(),this.prototype.hasOwnProperty(e)&&((t=Object.create(t)).wrapped=!0),this.elementProperties.set(e,t),!t.noAccessor){let n=Symbol(),s=this.getPropertyDescriptor(e,n,t);s!==void 0&&Ve(this.prototype,e,s)}}static getPropertyDescriptor(e,t,n){let{get:s,set:o}=Be(this.prototype,e)??{get(){return this[t]},set(r){this[t]=r}};return{get:s,set(r){let l=s?.call(this);o?.call(this,r),this.requestUpdate(e,l,n)},configurable:!0,enumerable:!0}}static getPropertyOptions(e){return this.elementProperties.get(e)??me}static _$Ei(){if(this.hasOwnProperty(P("elementProperties")))return;let e=Ke(this);e.finalize(),e.l!==void 0&&(this.l=[...e.l]),this.elementProperties=new Map(e.elementProperties)}static finalize(){if(this.hasOwnProperty(P("finalized")))return;if(this.finalized=!0,this._$Ei(),this.hasOwnProperty(P("properties"))){let t=this.properties,n=[...ze(t),...je(t)];for(let s of n)this.createProperty(s,t[s])}let e=this[Symbol.metadata];if(e!==null){let t=litPropertyMetadata.get(e);if(t!==void 0)for(let[n,s]of t)this.elementProperties.set(n,s)}this._$Eh=new Map;for(let[t,n]of this.elementProperties){let s=this._$Eu(t,n);s!==void 0&&this._$Eh.set(s,t)}this.elementStyles=this.finalizeStyles(this.styles)}static finalizeStyles(e){let t=[];if(Array.isArray(e)){let n=new Set(e.flat(1/0).reverse());for(let s of n)t.unshift(F(s))}else e!==void 0&&t.push(F(e));return t}static _$Eu(e,t){let n=t.attribute;return n===!1?void 0:typeof n=="string"?n:typeof e=="string"?e.toLowerCase():void 0}constructor(){super(),this._$Ep=void 0,this.isUpdatePending=!1,this.hasUpdated=!1,this._$Em=null,this._$Ev()}_$Ev(){this._$ES=new Promise(e=>this.enableUpdating=e),this._$AL=new Map,this._$E_(),this.requestUpdate(),this.constructor.l?.forEach(e=>e(this))}addController(e){(this._$EO??=new Set).add(e),this.renderRoot!==void 0&&this.isConnected&&e.hostConnected?.()}removeController(e){this._$EO?.delete(e)}_$E_(){let e=new Map,t=this.constructor.elementProperties;for(let n of t.keys())this.hasOwnProperty(n)&&(e.set(n,this[n]),delete this[n]);e.size>0&&(this._$Ep=e)}createRenderRoot(){let e=this.shadowRoot??this.attachShadow(this.constructor.shadowRootOptions);return le(e,this.constructor.elementStyles),e}connectedCallback(){this.renderRoot??=this.createRenderRoot(),this.enableUpdating(!0),this._$EO?.forEach(e=>e.hostConnected?.())}enableUpdating(e){}disconnectedCallback(){this._$EO?.forEach(e=>e.hostDisconnected?.())}attributeChangedCallback(e,t,n){this._$AK(e,n)}_$ET(e,t){let n=this.constructor.elementProperties.get(e),s=this.constructor._$Eu(e,n);if(s!==void 0&&n.reflect===!0){let o=(n.converter?.toAttribute!==void 0?n.converter:G).toAttribute(t,n.type);this._$Em=e,o==null?this.removeAttribute(s):this.setAttribute(s,o),this._$Em=null}}_$AK(e,t){let n=this.constructor,s=n._$Eh.get(e);if(s!==void 0&&this._$Em!==s){let o=n.getPropertyOptions(s),r=typeof o.converter=="function"?{fromAttribute:o.converter}:o.converter?.fromAttribute!==void 0?o.converter:G;this._$Em=s;let l=r.fromAttribute(t,o.type);this[s]=l??this._$Ej?.get(s)??l,this._$Em=null}}requestUpdate(e,t,n,s=!1,o){if(e!==void 0){let r=this.constructor;if(s===!1&&(o=this[e]),n??=r.getPropertyOptions(e),!((n.hasChanged??pe)(o,t)||n.useDefault&&n.reflect&&o===this._$Ej?.get(e)&&!this.hasAttribute(r._$Eu(e,n))))return;this.C(e,t,n)}this.isUpdatePending===!1&&(this._$ES=this._$EP())}C(e,t,{useDefault:n,reflect:s,wrapped:o},r){n&&!(this._$Ej??=new Map).has(e)&&(this._$Ej.set(e,r??t??this[e]),o!==!0||r!==void 0)||(this._$AL.has(e)||(this.hasUpdated||n||(t=void 0),this._$AL.set(e,t)),s===!0&&this._$Em!==e&&(this._$Eq??=new Set).add(e))}async _$EP(){this.isUpdatePending=!0;try{await this._$ES}catch(t){Promise.reject(t)}let e=this.scheduleUpdate();return e!=null&&await e,!this.isUpdatePending}scheduleUpdate(){return this.performUpdate()}performUpdate(){if(!this.isUpdatePending)return;if(!this.hasUpdated){if(this.renderRoot??=this.createRenderRoot(),this._$Ep){for(let[s,o]of this._$Ep)this[s]=o;this._$Ep=void 0}let n=this.constructor.elementProperties;if(n.size>0)for(let[s,o]of n){let{wrapped:r}=o,l=this[s];r!==!0||this._$AL.has(s)||l===void 0||this.C(s,void 0,o,l)}}let e=!1,t=this._$AL;try{e=this.shouldUpdate(t),e?(this.willUpdate(t),this._$EO?.forEach(n=>n.hostUpdate?.()),this.update(t)):this._$EM()}catch(n){throw e=!1,this._$EM(),n}e&&this._$AE(t)}willUpdate(e){}_$AE(e){this._$EO?.forEach(t=>t.hostUpdated?.()),this.hasUpdated||(this.hasUpdated=!0,this.firstUpdated(e)),this.updated(e)}_$EM(){this._$AL=new Map,this.isUpdatePending=!1}get updateComplete(){return this.getUpdateComplete()}getUpdateComplete(){return this._$ES}shouldUpdate(e){return!0}update(e){this._$Eq&&=this._$Eq.forEach(t=>this._$ET(t,this[t])),this._$EM()}updated(e){}firstUpdated(e){}};g.elementStyles=[],g.shadowRootOptions={mode:"open"},g[P("elementProperties")]=new Map,g[P("finalized")]=new Map,Fe?.({ReactiveElement:g}),(W.reactiveElementVersions??=[]).push("2.1.2");var te=globalThis,fe=i=>i,I=te.trustedTypes,ge=I?I.createPolicy("lit-html",{createHTML:i=>i}):void 0,$e="$lit$",w=`lit$${Math.random().toFixed(9).slice(2)}$`,Ae="?"+w,Ge=`<${Ae}>`,A=document,R=()=>A.createComment(""),M=i=>i===null||typeof i!="object"&&typeof i!="function",ne=Array.isArray,Ye=i=>ne(i)||typeof i?.[Symbol.iterator]=="function",Y=`[ 	
\f\r]`,H=/<(?:(!--|\/[^a-zA-Z])|(\/?[a-zA-Z][^>\s]*)|(\/?$))/g,ye=/-->/g,_e=/>/g,b=RegExp(`>|${Y}(?:([^\\s"'>=/]+)(${Y}*=${Y}*(?:[^ 	
\f\r"'\`<>=]|("|')|))|$)`,"g"),we=/'/g,ve=/"/g,ke=/^(?:script|style|textarea|title)$/i,ie=i=>(e,...t)=>({_$litType$:i,strings:e,values:t}),y=ie(1),gt=ie(2),yt=ie(3),k=Symbol.for("lit-noChange"),c=Symbol.for("lit-nothing"),be=new WeakMap,$=A.createTreeWalker(A,129);function Te(i,e){if(!ne(i)||!i.hasOwnProperty("raw"))throw Error("invalid template strings array");return ge!==void 0?ge.createHTML(e):e}var Je=(i,e)=>{let t=i.length-1,n=[],s,o=e===2?"<svg>":e===3?"<math>":"",r=H;for(let l=0;l<t;l++){let a=i[l],h,u,d=-1,m=0;for(;m<a.length&&(r.lastIndex=m,u=r.exec(a),u!==null);)m=r.lastIndex,r===H?u[1]==="!--"?r=ye:u[1]!==void 0?r=_e:u[2]!==void 0?(ke.test(u[2])&&(s=RegExp("</"+u[2],"g")),r=b):u[3]!==void 0&&(r=b):r===b?u[0]===">"?(r=s??H,d=-1):u[1]===void 0?d=-2:(d=r.lastIndex-u[2].length,h=u[1],r=u[3]===void 0?b:u[3]==='"'?ve:we):r===ve||r===we?r=b:r===ye||r===_e?r=H:(r=b,s=void 0);let p=r===b&&i[l+1].startsWith("/>")?" ":"";o+=r===H?a+Ge:d>=0?(n.push(h),a.slice(0,d)+$e+a.slice(d)+w+p):a+w+(d===-2?l:p)}return[Te(i,o+(i[t]||"<?>")+(e===2?"</svg>":e===3?"</math>":"")),n]},U=class i{constructor({strings:e,_$litType$:t},n){let s;this.parts=[];let o=0,r=0,l=e.length-1,a=this.parts,[h,u]=Je(e,t);if(this.el=i.createElement(h,n),$.currentNode=this.el.content,t===2||t===3){let d=this.el.content.firstChild;d.replaceWith(...d.childNodes)}for(;(s=$.nextNode())!==null&&a.length<l;){if(s.nodeType===1){if(s.hasAttributes())for(let d of s.getAttributeNames())if(d.endsWith($e)){let m=u[r++],p=s.getAttribute(d).split(w),v=/([.?@])?(.*)/.exec(m);a.push({type:1,index:o,name:v[2],strings:p,ctor:v[1]==="."?X:v[1]==="?"?Z:v[1]==="@"?Q:S}),s.removeAttribute(d)}else d.startsWith(w)&&(a.push({type:6,index:o}),s.removeAttribute(d));if(ke.test(s.tagName)){let d=s.textContent.split(w),m=d.length-1;if(m>0){s.textContent=I?I.emptyScript:"";for(let p=0;p<m;p++)s.append(d[p],R()),$.nextNode(),a.push({type:2,index:++o});s.append(d[m],R())}}}else if(s.nodeType===8)if(s.data===Ae)a.push({type:2,index:o});else{let d=-1;for(;(d=s.data.indexOf(w,d+1))!==-1;)a.push({type:7,index:o}),d+=w.length-1}o++}}static createElement(e,t){let n=A.createElement("template");return n.innerHTML=e,n}};function T(i,e,t=i,n){if(e===k)return e;let s=n!==void 0?t._$Co?.[n]:t._$Cl,o=M(e)?void 0:e._$litDirective$;return s?.constructor!==o&&(s?._$AO?.(!1),o===void 0?s=void 0:(s=new o(i),s._$AT(i,t,n)),n!==void 0?(t._$Co??=[])[n]=s:t._$Cl=s),s!==void 0&&(e=T(i,s._$AS(i,e.values),s,n)),e}var J=class{constructor(e,t){this._$AV=[],this._$AN=void 0,this._$AD=e,this._$AM=t}get parentNode(){return this._$AM.parentNode}get _$AU(){return this._$AM._$AU}u(e){let{el:{content:t},parts:n}=this._$AD,s=(e?.creationScope??A).importNode(t,!0);$.currentNode=s;let o=$.nextNode(),r=0,l=0,a=n[0];for(;a!==void 0;){if(r===a.index){let h;a.type===2?h=new O(o,o.nextSibling,this,e):a.type===1?h=new a.ctor(o,a.name,a.strings,this,e):a.type===6&&(h=new ee(o,this,e)),this._$AV.push(h),a=n[++l]}r!==a?.index&&(o=$.nextNode(),r++)}return $.currentNode=A,s}p(e){let t=0;for(let n of this._$AV)n!==void 0&&(n.strings!==void 0?(n._$AI(e,n,t),t+=n.strings.length-2):n._$AI(e[t])),t++}},O=class i{get _$AU(){return this._$AM?._$AU??this._$Cv}constructor(e,t,n,s){this.type=2,this._$AH=c,this._$AN=void 0,this._$AA=e,this._$AB=t,this._$AM=n,this.options=s,this._$Cv=s?.isConnected??!0}get parentNode(){let e=this._$AA.parentNode,t=this._$AM;return t!==void 0&&e?.nodeType===11&&(e=t.parentNode),e}get startNode(){return this._$AA}get endNode(){return this._$AB}_$AI(e,t=this){e=T(this,e,t),M(e)?e===c||e==null||e===""?(this._$AH!==c&&this._$AR(),this._$AH=c):e!==this._$AH&&e!==k&&this._(e):e._$litType$!==void 0?this.$(e):e.nodeType!==void 0?this.T(e):Ye(e)?this.k(e):this._(e)}O(e){return this._$AA.parentNode.insertBefore(e,this._$AB)}T(e){this._$AH!==e&&(this._$AR(),this._$AH=this.O(e))}_(e){this._$AH!==c&&M(this._$AH)?this._$AA.nextSibling.data=e:this.T(A.createTextNode(e)),this._$AH=e}$(e){let{values:t,_$litType$:n}=e,s=typeof n=="number"?this._$AC(e):(n.el===void 0&&(n.el=U.createElement(Te(n.h,n.h[0]),this.options)),n);if(this._$AH?._$AD===s)this._$AH.p(t);else{let o=new J(s,this),r=o.u(this.options);o.p(t),this.T(r),this._$AH=o}}_$AC(e){let t=be.get(e.strings);return t===void 0&&be.set(e.strings,t=new U(e)),t}k(e){ne(this._$AH)||(this._$AH=[],this._$AR());let t=this._$AH,n,s=0;for(let o of e)s===t.length?t.push(n=new i(this.O(R()),this.O(R()),this,this.options)):n=t[s],n._$AI(o),s++;s<t.length&&(this._$AR(n&&n._$AB.nextSibling,s),t.length=s)}_$AR(e=this._$AA.nextSibling,t){for(this._$AP?.(!1,!0,t);e!==this._$AB;){let n=fe(e).nextSibling;fe(e).remove(),e=n}}setConnected(e){this._$AM===void 0&&(this._$Cv=e,this._$AP?.(e))}},S=class{get tagName(){return this.element.tagName}get _$AU(){return this._$AM._$AU}constructor(e,t,n,s,o){this.type=1,this._$AH=c,this._$AN=void 0,this.element=e,this.name=t,this._$AM=s,this.options=o,n.length>2||n[0]!==""||n[1]!==""?(this._$AH=Array(n.length-1).fill(new String),this.strings=n):this._$AH=c}_$AI(e,t=this,n,s){let o=this.strings,r=!1;if(o===void 0)e=T(this,e,t,0),r=!M(e)||e!==this._$AH&&e!==k,r&&(this._$AH=e);else{let l=e,a,h;for(e=o[0],a=0;a<o.length-1;a++)h=T(this,l[n+a],t,a),h===k&&(h=this._$AH[a]),r||=!M(h)||h!==this._$AH[a],h===c?e=c:e!==c&&(e+=(h??"")+o[a+1]),this._$AH[a]=h}r&&!s&&this.j(e)}j(e){e===c?this.element.removeAttribute(this.name):this.element.setAttribute(this.name,e??"")}},X=class extends S{constructor(){super(...arguments),this.type=3}j(e){this.element[this.name]=e===c?void 0:e}},Z=class extends S{constructor(){super(...arguments),this.type=4}j(e){this.element.toggleAttribute(this.name,!!e&&e!==c)}},Q=class extends S{constructor(e,t,n,s,o){super(e,t,n,s,o),this.type=5}_$AI(e,t=this){if((e=T(this,e,t,0)??c)===k)return;let n=this._$AH,s=e===c&&n!==c||e.capture!==n.capture||e.once!==n.once||e.passive!==n.passive,o=e!==c&&(n===c||s);s&&this.element.removeEventListener(this.name,this,n),o&&this.element.addEventListener(this.name,this,e),this._$AH=e}handleEvent(e){typeof this._$AH=="function"?this._$AH.call(this.options?.host??this.element,e):this._$AH.handleEvent(e)}},ee=class{constructor(e,t,n){this.element=e,this.type=6,this._$AN=void 0,this._$AM=t,this.options=n}get _$AU(){return this._$AM._$AU}_$AI(e){T(this,e)}};var Xe=te.litHtmlPolyfillSupport;Xe?.(U,O),(te.litHtmlVersions??=[]).push("3.3.3");var Se=(i,e,t)=>{let n=t?.renderBefore??e,s=n._$litPart$;if(s===void 0){let o=t?.renderBefore??null;n._$litPart$=s=new O(e.insertBefore(R(),o),o,void 0,t??{})}return s._$AI(i),s};var se=globalThis,f=class extends g{constructor(){super(...arguments),this.renderOptions={host:this},this._$Do=void 0}createRenderRoot(){let e=super.createRenderRoot();return this.renderOptions.renderBefore??=e.firstChild,e}update(e){let t=this.render();this.hasUpdated||(this.renderOptions.isConnected=this.isConnected),super.update(e),this._$Do=Se(t,this.renderRoot,this.renderOptions)}connectedCallback(){super.connectedCallback(),this._$Do?.setConnected(!0)}disconnectedCallback(){super.disconnectedCallback(),this._$Do?.setConnected(!1)}render(){return k}};f._$litElement$=!0,f.finalized=!0,se.litElementHydrateSupport?.({LitElement:f});var Ze=se.litElementPolyfillSupport;Ze?.({LitElement:f});(se.litElementVersions??=[]).push("4.2.2");var Ee={card_entity_not_found:"Entity not found: {entity}",card_not_a_timer:"{entity} is not the Run for number of a Timerify timer",card_error_entity:"Choose the Run for number of a timer",card_error_layout:"The layout is pill or round",card_error_presets:"Presets are whole minutes from 1 to 1440",card_close:"Close",card_picker_description:"The countdown, presets and schedule of a Timerify timer"};var xe="common",Pe="timerify",et=`component.${Pe}.${xe}.`;function tt(i,e){return i.replace(/\{(\w+)\}/g,(t,n)=>String(e?.[n]??t))}function _(i,e,t){return i?.localize(et+e,t)||tt(Ee[e],t)}var N,Ce=Promise.resolve(),He,Re=new Set;function Me(i){return i.language!==N&&(N=i.language,Ce=nt(i,i.language)),Ce}async function nt(i,e){let t;try{t=await i.loadBackendTranslation(xe,Pe)}catch{N===e&&(N=void 0);return}N===e&&(He={...i,localize:t},Re.forEach(n=>n()))}function V(){return He}function Ue(i){Re.add(i)}var it=[15,30,45,60,120],st=1440,E=class extends Error{constructor(t){super(_(V(),t));this.key=t}key};function ot(i){let e=typeof i=="number"?i:typeof i=="string"&&/^\d+$/.test(i)?Number(i):void 0;return e!==void 0&&Number.isInteger(e)&&e>=1&&e<=st?e:void 0}function rt(i){if(i===void 0)return[...it];if(!Array.isArray(i)||i.length===0)throw new E("card_error_presets");let e=new Set;for(let t of i){let n=ot(t);if(n===void 0)throw new E("card_error_presets");e.add(n)}return[...e]}function Oe(i){let e=typeof i=="object"&&i!==null?i:{},{entity:t,layout:n="pill",name:s,icon:o}=e;if(typeof t!="string"||!/^number\.[a-z0-9_]+$/.test(t))throw new E("card_error_entity");if(n!=="pill"&&n!=="round")throw new E("card_error_layout");return{entity:t,layout:n,...typeof s=="string"&&s!==""&&{name:s},...typeof o=="string"&&o!==""&&{icon:o},presets:rt(e.presets)}}function oe(i){for(let e of i.composedPath()){if(e===i.currentTarget)return!1;if(e instanceof HTMLButtonElement)return!0}return!1}var B=class{#e;#t=!1;constructor(e,t){this.#e=t,e.addController(this)}hostDisconnected(){this.#t=!1}binding(){return{click:e=>{oe(e)||this.#e.tap()},keydown:e=>{oe(e)||(e.key==="Enter"?(e.preventDefault(),e.repeat||this.#e.tap()):e.key===" "&&(e.preventDefault(),this.#t=!0))},keyup:e=>{if(e.key!==" ")return;let t=this.#t;this.#t=!1,t&&!oe(e)&&this.#e.tap()}}}};var at="not_found";async function De(i,e){try{return{status:"found",info:await i.callWS({type:"timerify/timer",entity_id:e})}}catch(t){return{status:typeof t=="object"&&t!==null&&"code"in t&&t.code===at?"not_found":"failed"}}}function dt(i,e){return i===void 0||i.state==="unavailable"||i.state==="unknown"?!1:e.states.includes(i.state)===(e.match==="is")}var ht="mdi:timer-outline",Ne=i=>i===void 0||i.state==="unavailable";function Le(i){let e=typeof i=="string"?Date.parse(i):Number.NaN;return Number.isNaN(e)?void 0:e}function We(i,e,t,n){let s=t.status==="found"?t.info:void 0,o=i.states[e.entity],r=s&&i.states[s.target],l=e.name||r&&i.formatEntityName(r,void 0)||o?.attributes.friendly_name||e.entity,a=e.icon?{icon:e.icon}:r?{stateObj:r}:{icon:ht},h={name:l,icon:a,target:r,remaining:0},u=s&&i.states[s.ends_at];if(s===void 0||u===void 0||Ne(o)||Ne(u))return{...h,state:"unavailable",progress:0};let d=Le(u.state);if(d===void 0)return dt(r,s.target_on)?{...h,state:"open",progress:1}:{...h,state:"idle",progress:0};let m=Le(u.attributes.started_at),p=m===void 0?0:(d-m)/1e3,v=Math.max(0,(d-n)/1e3);return{...h,state:"counting",remaining:v,progress:p>0?Math.min(1,v/p):1,endsAt:new Date(d)}}function z(i,e){return e?[i,e.ends_at,e.next_command,e.target,...e.intervals.map(({entity_id:t})=>t)]:[i]}var ct=["locale","language","localize","config","user","connected","entities"];function j(i,e,t){for(let s of i.keys())if(s!=="hass")return!0;let n=i.get("hass");return n===void 0||e===void 0?!0:ct.some(s=>n[s]!==e[s])||t.some(s=>n.states[s]!==e.states[s])}var K=class extends f{static properties={hass:{attribute:!1},config:{attribute:!1},info:{attribute:!1},view:{attribute:!1},opened:{state:!0}};static styles=x`
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
  `;constructor(){super(),this.opened=!1}open(){this.opened=!0}close(){this.#e?.close(),this.#n()}disconnectedCallback(){super.disconnectedCallback(),this.close()}get#e(){return this.renderRoot.querySelector("dialog")}#t=()=>{this.#e?.open||this.#n()};#n(){this.opened&&(this.opened=!1,this.dispatchEvent(new CustomEvent("closed")))}shouldUpdate(e){if(!this.hasUpdated||e.has("opened"))return!0;let t=z(this.config.entity,this.info);return this.opened&&j(e,this.hass,t)}updated(e){let t=this.#e;e.has("opened")&&this.opened&&t&&!t.open&&t.showModal()}render(){return y`
      <dialog
        aria-labelledby="title"
        @cancel=${()=>this.close()}
        @close=${this.#t}
        @click=${e=>{e.target===e.currentTarget&&this.close()}}
      >
        ${this.opened?this.#i():c}
      </dialog>
    `}#i(){return y`
      <div class="wrapper">
        <header>
          <h2 id="title">${this.view.name}</h2>
          <button class="close" @click=${()=>this.close()}>
            ${_(this.hass,"card_close")}
          </button>
        </header>
      </div>
    `}};var re="timerify-card",lt={pill:{columns:6,rows:1,min_columns:3,min_rows:1,max_rows:1},round:{columns:3,rows:2,min_columns:2,min_rows:2,max_rows:3}},ae=i=>i!==void 0&&i.state!=="unavailable"&&i.state!=="unknown",de=class extends f{static properties={hass:{attribute:!1,noAccessor:!0},_config:{state:!0},_lookup:{state:!0}};static styles=x`
    :host {
      display: block;
    }
    ha-card {
      height: 100%;
    }
    .body {
      display: flex;
      align-items: center;
      gap: 12px;
      box-sizing: border-box;
      height: 100%;
      min-height: 56px;
      padding: 8px 16px;
      border-radius: inherit;
      cursor: pointer;
    }
    .body:focus-visible {
      outline: 2px solid var(--primary-color);
      outline-offset: 2px;
    }
    .name {
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    .warning {
      display: flex;
      align-items: center;
      gap: 12px;
      padding: 16px;
      color: var(--warning-color);
    }
  `;#e;#t=new Set;#n=!1;#i=!1;#a=new B(this,{tap:()=>this.#c?.open()});#s=this.#a.binding();constructor(){super(),this._lookup={status:"pending"}}get hass(){return this.#e}set hass(e){let t=this.#e;this.#e=e,this.requestUpdate("hass",t),this.#d(t,e)}setConfig(e){let t=Oe(e),n=this._config?.entity!==t.entity;this._config=t,n&&(this._lookup={status:"pending"},this.#r())}getCardSize(){return this._config?.layout==="round"?3:1}getGridOptions(){return lt[this._config?.layout??"pill"]}async getUpdateComplete(){let e=await super.getUpdateComplete();for(;this.#t.size>0;)await Promise.allSettled([...this.#t]),e=await super.getUpdateComplete();return e}#d(e,t){let n=e!==void 0&&t.connected&&!e.connected;(e===void 0||e.language!==t.language||n)&&this.#o(Me(t));let s=this._config?.entity;s!==void 0&&(e===void 0||e.entities!==t.entities||n||ae(t.states[s])&&!ae(e.states[s]))&&this.#r()}#o(e){let t=e.finally(()=>this.#t.delete(t));this.#t.add(t)}#r(){if(this.#n){this.#i=!0;return}this.#n=!0,this.#o(this.#h())}async#h(){try{do{this.#i=!1;let e=this._config?.entity;if(this.#e===void 0||e===void 0)return;let t=await De(this.#e,e);this.#i||(this._lookup=t)}while(this.#i)}finally{this.#n=!1}}shouldUpdate(e){let t=this._lookup.status==="found"?this._lookup.info:void 0,n=this._config?z(this._config.entity,t):[];return j(e,this.#e,n)}get#c(){return this.renderRoot.querySelector("timerify-card-popup")}#l(e,t){if(this._lookup.status!=="not_found")return;let n=e.states[t.entity];return n===void 0?_(e,"card_entity_not_found",{entity:t.entity}):ae(n)?_(e,"card_not_a_timer",{entity:t.entity}):void 0}render(){let e=this.#e,t=this._config;if(!e||!t)return c;let n=this.#l(e,t);if(n)return y`
        <ha-card>
          <div class="warning" role="alert">
            <ha-icon icon="mdi:alert-outline"></ha-icon>
            <span>${n}</span>
          </div>
        </ha-card>
      `;let s=We(e,t,this._lookup,Date.now()),o="stateObj"in s.icon?y`<ha-state-icon .stateObj=${s.icon.stateObj}></ha-state-icon>`:y`<ha-icon .icon=${s.icon.icon}></ha-icon>`;return y`
      <ha-card>
        <div
          class="body"
          role="button"
          tabindex="0"
          aria-haspopup="dialog"
          @click=${this.#s.click}
          @keydown=${this.#s.keydown}
          @keyup=${this.#s.keyup}
        >
          ${o}
          <span class="name">${s.name}</span>
        </div>
      </ha-card>
      ${this._lookup.status==="found"?y`
            <timerify-card-popup
              .hass=${e}
              .config=${t}
              .info=${this._lookup.info}
              .view=${s}
              @closed=${()=>this.renderRoot.querySelector(".body")?.focus()}
            ></timerify-card-popup>
          `:c}
    `}};if(!customElements.get(re)){customElements.define("timerify-card-popup",K),customElements.define(re,de);let i={type:re,name:"Timerify",description:_(void 0,"card_picker_description"),preview:!0,documentationURL:"https://github.com/klimofey/timerify#dashboard-card"};(window.customCards??=[]).push(i),Ue(()=>{i.description=_(V(),"card_picker_description")})}export{de as TimerifyCard};
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
*/
