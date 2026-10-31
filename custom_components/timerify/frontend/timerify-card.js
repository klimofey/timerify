var L=globalThis,I=L.ShadowRoot&&(L.ShadyCSS===void 0||L.ShadyCSS.nativeShadow)&&"adoptedStyleSheets"in Document.prototype&&"replace"in CSSStyleSheet.prototype,Y=Symbol(),le=new WeakMap,P=class{constructor(e,t,n){if(this._$cssResult$=!0,n!==Y)throw Error("CSSResult is not constructable. Use `unsafeCSS` or `css` instead.");this.cssText=e,this.t=t}get styleSheet(){let e=this.o,t=this.t;if(I&&e===void 0){let n=t!==void 0&&t.length===1;n&&(e=le.get(t)),e===void 0&&((this.o=e=new CSSStyleSheet).replaceSync(this.cssText),n&&le.set(t,e))}return e}toString(){return this.cssText}},ue=i=>new P(typeof i=="string"?i:i+"",void 0,Y),$=(i,...e)=>{let t=i.length===1?i[0]:e.reduce((n,o,s)=>n+(r=>{if(r._$cssResult$===!0)return r.cssText;if(typeof r=="number")return r;throw Error("Value passed to 'css' function must be a 'css' function result: "+r+". Use 'unsafeCSS' to pass non-literal values, but take care to ensure page security.")})(o)+i[s+1],i[0]);return new P(t,i,Y)},me=(i,e)=>{if(I)i.adoptedStyleSheets=e.map(t=>t instanceof CSSStyleSheet?t:t.styleSheet);else for(let t of e){let n=document.createElement("style"),o=L.litNonce;o!==void 0&&n.setAttribute("nonce",o),n.textContent=t.cssText,i.appendChild(n)}},Z=I?i=>i:i=>i instanceof CSSStyleSheet?(e=>{let t="";for(let n of e.cssRules)t+=n.cssText;return ue(t)})(i):i;var{is:et,defineProperty:tt,getOwnPropertyDescriptor:nt,getOwnPropertyNames:it,getOwnPropertySymbols:ot,getPrototypeOf:st}=Object,V=globalThis,pe=V.trustedTypes,rt=pe?pe.emptyScript:"",at=V.reactiveElementPolyfillSupport,H=(i,e)=>i,J={toAttribute(i,e){switch(e){case Boolean:i=i?rt:null;break;case Object:case Array:i=i==null?i:JSON.stringify(i)}return i},fromAttribute(i,e){let t=i;switch(e){case Boolean:t=i!==null;break;case Number:t=i===null?null:Number(i);break;case Object:case Array:try{t=JSON.parse(i)}catch{t=null}}return t}},ye=(i,e)=>!et(i,e),fe={attribute:!0,type:String,converter:J,reflect:!1,useDefault:!1,hasChanged:ye};Symbol.metadata??=Symbol("metadata"),V.litPropertyMetadata??=new WeakMap;var _=class extends HTMLElement{static addInitializer(e){this._$Ei(),(this.l??=[]).push(e)}static get observedAttributes(){return this.finalize(),this._$Eh&&[...this._$Eh.keys()]}static createProperty(e,t=fe){if(t.state&&(t.attribute=!1),this._$Ei(),this.prototype.hasOwnProperty(e)&&((t=Object.create(t)).wrapped=!0),this.elementProperties.set(e,t),!t.noAccessor){let n=Symbol(),o=this.getPropertyDescriptor(e,n,t);o!==void 0&&tt(this.prototype,e,o)}}static getPropertyDescriptor(e,t,n){let{get:o,set:s}=nt(this.prototype,e)??{get(){return this[t]},set(r){this[t]=r}};return{get:o,set(r){let c=o?.call(this);s?.call(this,r),this.requestUpdate(e,c,n)},configurable:!0,enumerable:!0}}static getPropertyOptions(e){return this.elementProperties.get(e)??fe}static _$Ei(){if(this.hasOwnProperty(H("elementProperties")))return;let e=st(this);e.finalize(),e.l!==void 0&&(this.l=[...e.l]),this.elementProperties=new Map(e.elementProperties)}static finalize(){if(this.hasOwnProperty(H("finalized")))return;if(this.finalized=!0,this._$Ei(),this.hasOwnProperty(H("properties"))){let t=this.properties,n=[...it(t),...ot(t)];for(let o of n)this.createProperty(o,t[o])}let e=this[Symbol.metadata];if(e!==null){let t=litPropertyMetadata.get(e);if(t!==void 0)for(let[n,o]of t)this.elementProperties.set(n,o)}this._$Eh=new Map;for(let[t,n]of this.elementProperties){let o=this._$Eu(t,n);o!==void 0&&this._$Eh.set(o,t)}this.elementStyles=this.finalizeStyles(this.styles)}static finalizeStyles(e){let t=[];if(Array.isArray(e)){let n=new Set(e.flat(1/0).reverse());for(let o of n)t.unshift(Z(o))}else e!==void 0&&t.push(Z(e));return t}static _$Eu(e,t){let n=t.attribute;return n===!1?void 0:typeof n=="string"?n:typeof e=="string"?e.toLowerCase():void 0}constructor(){super(),this._$Ep=void 0,this.isUpdatePending=!1,this.hasUpdated=!1,this._$Em=null,this._$Ev()}_$Ev(){this._$ES=new Promise(e=>this.enableUpdating=e),this._$AL=new Map,this._$E_(),this.requestUpdate(),this.constructor.l?.forEach(e=>e(this))}addController(e){(this._$EO??=new Set).add(e),this.renderRoot!==void 0&&this.isConnected&&e.hostConnected?.()}removeController(e){this._$EO?.delete(e)}_$E_(){let e=new Map,t=this.constructor.elementProperties;for(let n of t.keys())this.hasOwnProperty(n)&&(e.set(n,this[n]),delete this[n]);e.size>0&&(this._$Ep=e)}createRenderRoot(){let e=this.shadowRoot??this.attachShadow(this.constructor.shadowRootOptions);return me(e,this.constructor.elementStyles),e}connectedCallback(){this.renderRoot??=this.createRenderRoot(),this.enableUpdating(!0),this._$EO?.forEach(e=>e.hostConnected?.())}enableUpdating(e){}disconnectedCallback(){this._$EO?.forEach(e=>e.hostDisconnected?.())}attributeChangedCallback(e,t,n){this._$AK(e,n)}_$ET(e,t){let n=this.constructor.elementProperties.get(e),o=this.constructor._$Eu(e,n);if(o!==void 0&&n.reflect===!0){let s=(n.converter?.toAttribute!==void 0?n.converter:J).toAttribute(t,n.type);this._$Em=e,s==null?this.removeAttribute(o):this.setAttribute(o,s),this._$Em=null}}_$AK(e,t){let n=this.constructor,o=n._$Eh.get(e);if(o!==void 0&&this._$Em!==o){let s=n.getPropertyOptions(o),r=typeof s.converter=="function"?{fromAttribute:s.converter}:s.converter?.fromAttribute!==void 0?s.converter:J;this._$Em=o;let c=r.fromAttribute(t,s.type);this[o]=c??this._$Ej?.get(o)??c,this._$Em=null}}requestUpdate(e,t,n,o=!1,s){if(e!==void 0){let r=this.constructor;if(o===!1&&(s=this[e]),n??=r.getPropertyOptions(e),!((n.hasChanged??ye)(s,t)||n.useDefault&&n.reflect&&s===this._$Ej?.get(e)&&!this.hasAttribute(r._$Eu(e,n))))return;this.C(e,t,n)}this.isUpdatePending===!1&&(this._$ES=this._$EP())}C(e,t,{useDefault:n,reflect:o,wrapped:s},r){n&&!(this._$Ej??=new Map).has(e)&&(this._$Ej.set(e,r??t??this[e]),s!==!0||r!==void 0)||(this._$AL.has(e)||(this.hasUpdated||n||(t=void 0),this._$AL.set(e,t)),o===!0&&this._$Em!==e&&(this._$Eq??=new Set).add(e))}async _$EP(){this.isUpdatePending=!0;try{await this._$ES}catch(t){Promise.reject(t)}let e=this.scheduleUpdate();return e!=null&&await e,!this.isUpdatePending}scheduleUpdate(){return this.performUpdate()}performUpdate(){if(!this.isUpdatePending)return;if(!this.hasUpdated){if(this.renderRoot??=this.createRenderRoot(),this._$Ep){for(let[o,s]of this._$Ep)this[o]=s;this._$Ep=void 0}let n=this.constructor.elementProperties;if(n.size>0)for(let[o,s]of n){let{wrapped:r}=s,c=this[o];r!==!0||this._$AL.has(o)||c===void 0||this.C(o,void 0,s,c)}}let e=!1,t=this._$AL;try{e=this.shouldUpdate(t),e?(this.willUpdate(t),this._$EO?.forEach(n=>n.hostUpdate?.()),this.update(t)):this._$EM()}catch(n){throw e=!1,this._$EM(),n}e&&this._$AE(t)}willUpdate(e){}_$AE(e){this._$EO?.forEach(t=>t.hostUpdated?.()),this.hasUpdated||(this.hasUpdated=!0,this.firstUpdated(e)),this.updated(e)}_$EM(){this._$AL=new Map,this.isUpdatePending=!1}get updateComplete(){return this.getUpdateComplete()}getUpdateComplete(){return this._$ES}shouldUpdate(e){return!0}update(e){this._$Eq&&=this._$Eq.forEach(t=>this._$ET(t,this[t])),this._$EM()}updated(e){}firstUpdated(e){}};_.elementStyles=[],_.shadowRootOptions={mode:"open"},_[H("elementProperties")]=new Map,_[H("finalized")]=new Map,at?.({ReactiveElement:_}),(V.reactiveElementVersions??=[]).push("2.1.2");var oe=globalThis,ge=i=>i,W=oe.trustedTypes,_e=W?W.createPolicy("lit-html",{createHTML:i=>i}):void 0,Te="$lit$",w=`lit$${Math.random().toFixed(9).slice(2)}$`,ke="?"+w,dt=`<${ke}>`,k=document,M=()=>k.createComment(""),U=i=>i===null||typeof i!="object"&&typeof i!="function",se=Array.isArray,ht=i=>se(i)||typeof i?.[Symbol.iterator]=="function",X=`[ 	
\f\r]`,R=/<(?:(!--|\/[^a-zA-Z])|(\/?[a-zA-Z][^>\s]*)|(\/?$))/g,ve=/-->/g,we=/>/g,A=RegExp(`>|${X}(?:([^\\s"'>=/]+)(${X}*=${X}*(?:[^ 	
\f\r"'\`<>=]|("|')|))|$)`,"g"),be=/'/g,$e=/"/g,xe=/^(?:script|style|textarea|title)$/i,re=i=>(e,...t)=>({_$litType$:i,strings:e,values:t}),m=re(1),Nt=re(2),Lt=re(3),v=Symbol.for("lit-noChange"),h=Symbol.for("lit-nothing"),Ae=new WeakMap,T=k.createTreeWalker(k,129);function Se(i,e){if(!se(i)||!i.hasOwnProperty("raw"))throw Error("invalid template strings array");return _e!==void 0?_e.createHTML(e):e}var ct=(i,e)=>{let t=i.length-1,n=[],o,s=e===2?"<svg>":e===3?"<math>":"",r=R;for(let c=0;c<t;c++){let a=i[c],l,u,d=-1,p=0;for(;p<a.length&&(r.lastIndex=p,u=r.exec(a),u!==null);)p=r.lastIndex,r===R?u[1]==="!--"?r=ve:u[1]!==void 0?r=we:u[2]!==void 0?(xe.test(u[2])&&(o=RegExp("</"+u[2],"g")),r=A):u[3]!==void 0&&(r=A):r===A?u[0]===">"?(r=o??R,d=-1):u[1]===void 0?d=-2:(d=r.lastIndex-u[2].length,l=u[1],r=u[3]===void 0?A:u[3]==='"'?$e:be):r===$e||r===be?r=A:r===ve||r===we?r=R:(r=A,o=void 0);let y=r===A&&i[c+1].startsWith("/>")?" ":"";s+=r===R?a+dt:d>=0?(n.push(l),a.slice(0,d)+Te+a.slice(d)+w+y):a+w+(d===-2?c:y)}return[Se(i,s+(i[t]||"<?>")+(e===2?"</svg>":e===3?"</math>":"")),n]},O=class i{constructor({strings:e,_$litType$:t},n){let o;this.parts=[];let s=0,r=0,c=e.length-1,a=this.parts,[l,u]=ct(e,t);if(this.el=i.createElement(l,n),T.currentNode=this.el.content,t===2||t===3){let d=this.el.content.firstChild;d.replaceWith(...d.childNodes)}for(;(o=T.nextNode())!==null&&a.length<c;){if(o.nodeType===1){if(o.hasAttributes())for(let d of o.getAttributeNames())if(d.endsWith(Te)){let p=u[r++],y=o.getAttribute(d).split(w),b=/([.?@])?(.*)/.exec(p);a.push({type:1,index:s,name:b[2],strings:y,ctor:b[1]==="."?ee:b[1]==="?"?te:b[1]==="@"?ne:C}),o.removeAttribute(d)}else d.startsWith(w)&&(a.push({type:6,index:s}),o.removeAttribute(d));if(xe.test(o.tagName)){let d=o.textContent.split(w),p=d.length-1;if(p>0){o.textContent=W?W.emptyScript:"";for(let y=0;y<p;y++)o.append(d[y],M()),T.nextNode(),a.push({type:2,index:++s});o.append(d[p],M())}}}else if(o.nodeType===8)if(o.data===ke)a.push({type:2,index:s});else{let d=-1;for(;(d=o.data.indexOf(w,d+1))!==-1;)a.push({type:7,index:s}),d+=w.length-1}s++}}static createElement(e,t){let n=k.createElement("template");return n.innerHTML=e,n}};function S(i,e,t=i,n){if(e===v)return e;let o=n!==void 0?t._$Co?.[n]:t._$Cl,s=U(e)?void 0:e._$litDirective$;return o?.constructor!==s&&(o?._$AO?.(!1),s===void 0?o=void 0:(o=new s(i),o._$AT(i,t,n)),n!==void 0?(t._$Co??=[])[n]=o:t._$Cl=o),o!==void 0&&(e=S(i,o._$AS(i,e.values),o,n)),e}var Q=class{constructor(e,t){this._$AV=[],this._$AN=void 0,this._$AD=e,this._$AM=t}get parentNode(){return this._$AM.parentNode}get _$AU(){return this._$AM._$AU}u(e){let{el:{content:t},parts:n}=this._$AD,o=(e?.creationScope??k).importNode(t,!0);T.currentNode=o;let s=T.nextNode(),r=0,c=0,a=n[0];for(;a!==void 0;){if(r===a.index){let l;a.type===2?l=new D(s,s.nextSibling,this,e):a.type===1?l=new a.ctor(s,a.name,a.strings,this,e):a.type===6&&(l=new ie(s,this,e)),this._$AV.push(l),a=n[++c]}r!==a?.index&&(s=T.nextNode(),r++)}return T.currentNode=k,o}p(e){let t=0;for(let n of this._$AV)n!==void 0&&(n.strings!==void 0?(n._$AI(e,n,t),t+=n.strings.length-2):n._$AI(e[t])),t++}},D=class i{get _$AU(){return this._$AM?._$AU??this._$Cv}constructor(e,t,n,o){this.type=2,this._$AH=h,this._$AN=void 0,this._$AA=e,this._$AB=t,this._$AM=n,this.options=o,this._$Cv=o?.isConnected??!0}get parentNode(){let e=this._$AA.parentNode,t=this._$AM;return t!==void 0&&e?.nodeType===11&&(e=t.parentNode),e}get startNode(){return this._$AA}get endNode(){return this._$AB}_$AI(e,t=this){e=S(this,e,t),U(e)?e===h||e==null||e===""?(this._$AH!==h&&this._$AR(),this._$AH=h):e!==this._$AH&&e!==v&&this._(e):e._$litType$!==void 0?this.$(e):e.nodeType!==void 0?this.T(e):ht(e)?this.k(e):this._(e)}O(e){return this._$AA.parentNode.insertBefore(e,this._$AB)}T(e){this._$AH!==e&&(this._$AR(),this._$AH=this.O(e))}_(e){this._$AH!==h&&U(this._$AH)?this._$AA.nextSibling.data=e:this.T(k.createTextNode(e)),this._$AH=e}$(e){let{values:t,_$litType$:n}=e,o=typeof n=="number"?this._$AC(e):(n.el===void 0&&(n.el=O.createElement(Se(n.h,n.h[0]),this.options)),n);if(this._$AH?._$AD===o)this._$AH.p(t);else{let s=new Q(o,this),r=s.u(this.options);s.p(t),this.T(r),this._$AH=s}}_$AC(e){let t=Ae.get(e.strings);return t===void 0&&Ae.set(e.strings,t=new O(e)),t}k(e){se(this._$AH)||(this._$AH=[],this._$AR());let t=this._$AH,n,o=0;for(let s of e)o===t.length?t.push(n=new i(this.O(M()),this.O(M()),this,this.options)):n=t[o],n._$AI(s),o++;o<t.length&&(this._$AR(n&&n._$AB.nextSibling,o),t.length=o)}_$AR(e=this._$AA.nextSibling,t){for(this._$AP?.(!1,!0,t);e!==this._$AB;){let n=ge(e).nextSibling;ge(e).remove(),e=n}}setConnected(e){this._$AM===void 0&&(this._$Cv=e,this._$AP?.(e))}},C=class{get tagName(){return this.element.tagName}get _$AU(){return this._$AM._$AU}constructor(e,t,n,o,s){this.type=1,this._$AH=h,this._$AN=void 0,this.element=e,this.name=t,this._$AM=o,this.options=s,n.length>2||n[0]!==""||n[1]!==""?(this._$AH=Array(n.length-1).fill(new String),this.strings=n):this._$AH=h}_$AI(e,t=this,n,o){let s=this.strings,r=!1;if(s===void 0)e=S(this,e,t,0),r=!U(e)||e!==this._$AH&&e!==v,r&&(this._$AH=e);else{let c=e,a,l;for(e=s[0],a=0;a<s.length-1;a++)l=S(this,c[n+a],t,a),l===v&&(l=this._$AH[a]),r||=!U(l)||l!==this._$AH[a],l===h?e=h:e!==h&&(e+=(l??"")+s[a+1]),this._$AH[a]=l}r&&!o&&this.j(e)}j(e){e===h?this.element.removeAttribute(this.name):this.element.setAttribute(this.name,e??"")}},ee=class extends C{constructor(){super(...arguments),this.type=3}j(e){this.element[this.name]=e===h?void 0:e}},te=class extends C{constructor(){super(...arguments),this.type=4}j(e){this.element.toggleAttribute(this.name,!!e&&e!==h)}},ne=class extends C{constructor(e,t,n,o,s){super(e,t,n,o,s),this.type=5}_$AI(e,t=this){if((e=S(this,e,t,0)??h)===v)return;let n=this._$AH,o=e===h&&n!==h||e.capture!==n.capture||e.once!==n.once||e.passive!==n.passive,s=e!==h&&(n===h||o);o&&this.element.removeEventListener(this.name,this,n),s&&this.element.addEventListener(this.name,this,e),this._$AH=e}handleEvent(e){typeof this._$AH=="function"?this._$AH.call(this.options?.host??this.element,e):this._$AH.handleEvent(e)}},ie=class{constructor(e,t,n){this.element=e,this.type=6,this._$AN=void 0,this._$AM=t,this.options=n}get _$AU(){return this._$AM._$AU}_$AI(e){S(this,e)}};var lt=oe.litHtmlPolyfillSupport;lt?.(O,D),(oe.litHtmlVersions??=[]).push("3.3.3");var Ce=(i,e,t)=>{let n=t?.renderBefore??e,o=n._$litPart$;if(o===void 0){let s=t?.renderBefore??null;n._$litPart$=o=new D(e.insertBefore(M(),s),s,void 0,t??{})}return o._$AI(i),o};var ae=globalThis,g=class extends _{constructor(){super(...arguments),this.renderOptions={host:this},this._$Do=void 0}createRenderRoot(){let e=super.createRenderRoot();return this.renderOptions.renderBefore??=e.firstChild,e}update(e){let t=this.render();this.hasUpdated||(this.renderOptions.isConnected=this.isConnected),super.update(e),this._$Do=Ce(t,this.renderRoot,this.renderOptions)}connectedCallback(){super.connectedCallback(),this._$Do?.setConnected(!0)}disconnectedCallback(){super.disconnectedCallback(),this._$Do?.setConnected(!1)}render(){return v}};g._$litElement$=!0,g.finalized=!0,ae.litElementHydrateSupport?.({LitElement:g});var ut=ae.litElementPolyfillSupport;ut?.({LitElement:g});(ae.litElementVersions??=[]).push("4.2.2");async function mt(i,e,t,n,o){try{await i.callService(e,t,n,{entity_id:o})}catch{}}function Ee(i,e,t){return mt(i,"timerify","add_time",{minutes:t},e)}var Pe={card_entity_not_found:"Entity not found: {entity}",card_not_a_timer:"{entity} is not the Run for number of a Timerify timer",card_error_entity:"Choose the Run for number of a timer",card_error_layout:"The layout is pill or round",card_error_presets:"Presets are whole minutes from 1 to 1440",card_error_chip:"The quick chip is whole minutes from 1 to 1440",card_close:"Close",card_until:"until {time}",card_add_time:"Add {duration}",card_picker_description:"The countdown, presets and schedule of a Timerify timer"};var Re="common",Me="timerify",ft=`component.${Me}.${Re}.`;function yt(i,e){return i.replace(/\{(\w+)\}/g,(t,n)=>String(e?.[n]??t))}function f(i,e,t){return i?.localize(ft+e,t)||yt(Pe[e],t)}var N,He=Promise.resolve(),Ue,Oe=new Set;function De(i){return i.language!==N&&(N=i.language,He=gt(i,i.language)),He}async function gt(i,e){let t;try{t=await i.loadBackendTranslation(Re,Me)}catch{N===e&&(N=void 0);return}N===e&&(Ue={...i,localize:t},Oe.forEach(n=>n()))}function z(){return Ue}function Ne(i){Oe.add(i)}var _t=[15,30,45,60,120],vt=1440,x=class extends Error{constructor(t){super(f(z(),t));this.key=t}key};function Le(i){let e=typeof i=="number"?i:typeof i=="string"&&/^\d+$/.test(i)?Number(i):void 0;return e!==void 0&&Number.isInteger(e)&&e>=1&&e<=vt?e:void 0}function wt(i){if(i===void 0)return[..._t];if(!Array.isArray(i)||i.length===0)throw new x("card_error_presets");let e=new Set;for(let t of i){let n=Le(t);if(n===void 0)throw new x("card_error_presets");e.add(n)}return[...e]}function bt(i){if(i===void 0)return;let e=Le(i);if(e===void 0)throw new x("card_error_chip");return e}function Ie(i){let e=typeof i=="object"&&i!==null?i:{},{entity:t,layout:n="pill",name:o,icon:s}=e;if(typeof t!="string"||!/^number\.[a-z0-9_]+$/.test(t))throw new x("card_error_entity");if(n!=="pill"&&n!=="round")throw new x("card_error_layout");let r=bt(e.chip);return{entity:t,layout:n,...typeof o=="string"&&o!==""&&{name:o},...typeof s=="string"&&s!==""&&{icon:s},presets:wt(e.presets),...r!==void 0&&{chip:r}}}var B=class{#e;#t;#i=!1;#n;constructor(e,t){this.#e=e,this.#t=t,e.addController(this)}hostConnected(){this.#i=!0,this.#o()}hostUpdated(){this.#o()}hostDisconnected(){this.#i=!1,this.#o()}#o(){let e=this.#t(),t=this.#i&&e!==void 0&&e.getTime()>Date.now();t&&this.#n===void 0?this.#n=setInterval(()=>this.#e.requestUpdate(),1e3):!t&&this.#n!==void 0&&(clearInterval(this.#n),this.#n=void 0)}};var Ve={ATTRIBUTE:1,CHILD:2,PROPERTY:3,BOOLEAN_ATTRIBUTE:4,EVENT:5,ELEMENT:6},We=i=>(...e)=>({_$litDirective$:i,values:e}),j=class{constructor(e){}get _$AU(){return this._$AM._$AU}_$AT(e,t,n){this._$Ct=e,this._$AM=t,this._$Ci=n}_$AS(e,t){return this.update(e,t)}update(e,t){return this.render(...t)}};var ze="important",$t=" !"+ze,Be=We(class extends j{constructor(i){if(super(i),i.type!==Ve.ATTRIBUTE||i.name!=="style"||i.strings?.length>2)throw Error("The `styleMap` directive must be used in the `style` attribute and must be the only part in the attribute.")}render(i){return Object.keys(i).reduce((e,t)=>{let n=i[t];return n==null?e:e+`${t=t.includes("-")?t:t.replace(/(?:^(webkit|moz|ms|o)|)(?=[A-Z])/g,"-$&").toLowerCase()}:${n};`},"")}update(i,[e]){let{style:t}=i.element;if(this.ft===void 0)return this.ft=new Set(Object.keys(e)),this.render(e);for(let n of this.ft)e[n]==null&&(this.ft.delete(n),n.includes("-")?t.removeProperty(n):t[n]=null);for(let n in e){let o=e[n];if(o!=null){this.ft.add(n);let s=typeof o=="string"&&o.endsWith($t);n.includes("-")||s?t.setProperty(n,s?o.slice(0,-11):o,s?ze:""):t[n]=o}}return v}});var je=i=>String(i).padStart(2,"0");function Ke(i){let e=Math.ceil(Math.max(0,i)),t=Math.floor(e/3600),n=Math.floor(e%3600/60),o=je(e%60);return t>0?`${t}:${je(n)}:${o}`:`${n}:${o}`}function At({language:i,time_format:e}){if(e==="12"||e==="24")return e==="12";let t=new Intl.DateTimeFormat(e==="language"?i:void 0,{hour:"numeric"}).resolvedOptions();return t.hourCycle==="h11"||t.hourCycle==="h12"}var Tt=864e5;function Fe(i,e){let t=new Intl.DateTimeFormat("en-US",{timeZone:i,year:"numeric",month:"numeric",day:"numeric"}).formatToParts(e),n=o=>Number(t.find(s=>s.type===o)?.value);return Date.UTC(n("year"),n("month")-1,n("day"))/Tt}function qe(i,e,t){let{locale:n}=i,o=n.time_zone==="server"?i.config.time_zone:void 0,s=Fe(o,e.getTime())-Fe(o,t),r=s===0?{}:s>=1&&s<=6?{weekday:"short"}:{month:"short",day:"numeric"};return new Intl.DateTimeFormat(n.language,{...r,hour:"numeric",minute:"2-digit",hourCycle:At(n)?"h12":"h23",timeZone:o}).format(e)}function de(i,e){let t=(r,c)=>new Intl.NumberFormat(i.locale.language,{style:"unit",unit:c,unitDisplay:"short",useGrouping:!1}).format(r),n=Math.floor(e/60),o=e%60,s=n>0?[t(n,"hour")]:[];return(o>0||n===0)&&s.push(t(o,"minute")),s.join(" ")}var kt="not_found";async function Ze(i,e){try{return{status:"found",info:await i.callWS({type:"timerify/timer",entity_id:e})}}catch(t){return{status:typeof t=="object"&&t!==null&&"code"in t&&t.code===kt?"not_found":"failed"}}}var E=i=>i!==void 0&&i.state!=="unavailable"&&i.state!=="unknown";function xt(i,e){return i===void 0||i.state==="unavailable"||i.state==="unknown"?!1:e.states.includes(i.state)===(e.match==="is")}var St="mdi:timer-outline",Ge=i=>i===void 0||i.state==="unavailable";function Ye(i){let e=typeof i=="string"?Date.parse(i):Number.NaN;return Number.isNaN(e)?void 0:e}function Je(i,e,t,n){let o=t.status==="found"?t.info:void 0,s=i.states[e.entity],r=o&&i.states[o.target],c=e.name||r&&i.formatEntityName(r,void 0)||s?.attributes.friendly_name||e.entity,a=e.icon?{icon:e.icon}:r?{stateObj:r}:{icon:St},l={name:c,icon:a,target:r,remaining:0},u=o&&i.states[o.ends_at];if(o===void 0||u===void 0||Ge(s)||Ge(u))return{...l,state:"unavailable",progress:0};let d=Ye(u.state);if(d===void 0)return xt(r,o.target_on)?{...l,state:"open",progress:1}:{...l,state:"idle",progress:0};let p=Ye(u.attributes.started_at),y=p===void 0?0:(d-p)/1e3,b=Math.max(0,(d-n)/1e3);return{...l,state:"counting",remaining:b,progress:y>0?Math.min(1,b/y):1,endsAt:new Date(d)}}function F(i,e){return e?[i,e.ends_at,e.next_command,e.target,...e.intervals.map(({entity_id:t})=>t)]:[i]}var Ct=["locale","language","localize","config","user","connected","entities"];function K(i,e,t){for(let o of i.keys())if(o!=="hass")return!0;let n=i.get("hass");return n===void 0||e===void 0?!0:Ct.some(o=>n[o]!==e[o])||t.some(o=>n.states[o]!==e.states[o])}function Et(i){return"stateObj"in i.icon?m`<ha-state-icon .stateObj=${i.icon.stateObj}></ha-state-icon>`:m`<ha-icon .icon=${i.icon.icon}></ha-icon>`}function Pt(i,e,t){if(i.state!=="unavailable")return i.target?t.formatEntityState(i.target):"";let n=t.states[e.entity];if(E(n))return"";let o={entity_id:e.entity,state:"unavailable",attributes:{}};return t.formatEntityState(n??o,"unavailable")}function Ht(i,e,t,n){if(i.state!=="counting"||i.endsAt===void 0)return Pt(i,e,t);let o=qe(t,i.endsAt,n);return m`
    <span class="remaining">${Ke(i.remaining)}</span>
    <span class="until">${f(t,"card_until",{time:o})}</span>
  `}function Xe(i,e,t,n,o,s){let r=Math.round(i.progress*1e3)/10;return m`
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
          <span class="fill" style=${Be({width:`${r}%`})}></span>
        </span>
      </div>
      <div class="content">
        <span class="icon">${Et(i)}</span>
        <span class="text" id="label">
          <span class="name">${i.name}</span>
          <span class="status">${Ht(i,e,t,s)}</span>
        </span>
        ${e.chip===void 0?h:m`
              <button
                class="chip"
                type="button"
                aria-label=${f(t,"card_add_time",{duration:de(t,e.chip)})}
                @click=${o}
              >
                +${de(t,e.chip)}
              </button>
            `}
      </div>
    </ha-card>
  `}var Qe=$`
  ha-card.pill {
    --timerify-radius: 28px;
    height: 56px;
    border-radius: var(--timerify-radius);
  }
  .body {
    position: absolute;
    inset: 0;
    border-radius: var(--timerify-radius);
    cursor: pointer;
  }
  .body:focus-visible {
    outline: 2px solid var(--primary-color);
    outline-offset: 2px;
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
  .content {
    position: relative;
    display: flex;
    align-items: center;
    gap: 12px;
    box-sizing: border-box;
    height: 100%;
    padding: 0 12px 0 8px;
    /* A press anywhere on the card reaches the body underneath, except on the chip. */
    pointer-events: none;
  }
  .icon {
    display: flex;
    flex: none;
    align-items: center;
    justify-content: center;
    width: 40px;
    height: 40px;
    color: var(--state-icon-color, var(--secondary-text-color));
  }
  .counting .icon,
  .open .icon {
    color: var(--state-active-color, var(--primary-color));
  }
  .unavailable .icon {
    color: var(--state-unavailable-color, var(--disabled-text-color));
  }
  .text {
    display: flex;
    flex: 1 1 auto;
    flex-direction: column;
    min-width: 0;
  }
  .name {
    overflow: hidden;
    color: var(--primary-text-color);
    font-size: var(--ha-font-size-m, 14px);
    font-weight: var(--ha-font-weight-medium, 500);
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .status {
    display: flex;
    gap: 6px;
    overflow: hidden;
    color: var(--secondary-text-color);
    font-size: var(--ha-font-size-s, 12px);
    white-space: nowrap;
  }
  .remaining {
    font-variant-numeric: tabular-nums;
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
`;var q=class extends g{static properties={hass:{attribute:!1},config:{attribute:!1},info:{attribute:!1},view:{attribute:!1},opened:{state:!0}};static styles=$`
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
  `;constructor(){super(),this.opened=!1}open(){this.opened=!0}close(){this.#e?.close(),this.#i()}disconnectedCallback(){super.disconnectedCallback(),this.close()}get#e(){return this.renderRoot.querySelector("dialog")}#t=()=>{this.#e?.open||this.#i()};#i(){this.opened&&(this.opened=!1,this.dispatchEvent(new CustomEvent("closed")))}shouldUpdate(e){if(!this.hasUpdated||e.has("opened"))return!0;let t=F(this.config.entity,this.info);return this.opened&&K(e,this.hass,t)}updated(e){let t=this.#e;e.has("opened")&&this.opened&&t&&!t.open&&t.showModal()}render(){return m`
      <dialog
        aria-labelledby="title"
        @cancel=${()=>this.close()}
        @close=${this.#t}
        @click=${e=>{e.target===e.currentTarget&&this.close()}}
      >
        ${this.opened?this.#n():h}
      </dialog>
    `}#n(){return m`
      <div class="wrapper">
        <header>
          <h2 id="title">${this.view.name}</h2>
          <button class="close" @click=${()=>this.close()}>
            ${f(this.hass,"card_close")}
          </button>
        </header>
      </div>
    `}};var G=class{#e;#t=!1;constructor(e,t){this.#e=t,e.addController(this)}hostDisconnected(){this.#t=!1}binding(){return{click:()=>this.#e.tap(),keydown:e=>{e.key==="Enter"?(e.preventDefault(),e.repeat||this.#e.tap()):e.key===" "&&(e.preventDefault(),this.#t=!0)},keyup:e=>{if(e.key!==" ")return;let t=this.#t;this.#t=!1,t&&this.#e.tap()}}}};var he="timerify-card",Rt={pill:{columns:6,rows:1,min_columns:3,min_rows:1,max_rows:1},round:{columns:3,rows:2,min_columns:2,min_rows:2,max_rows:3}},ce=class extends g{static properties={hass:{attribute:!1,noAccessor:!0},_config:{state:!0},_lookup:{state:!0}};static styles=[Qe,$`
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
    `];#e;#t=new Set;#i=!1;#n=!1;#o=new G(this,{tap:()=>this.#u?.open()});#d=this.#o.binding();#h=()=>{let{_config:e,hass:t}=this;e?.chip!==void 0&&t!==void 0&&Ee(t,e.entity,e.chip)};#s;constructor(){super(),this._lookup={status:"pending"},new B(this,()=>this.#s?.endsAt)}get hass(){return this.#e}set hass(e){let t=this.#e;this.#e=e,this.requestUpdate("hass",t),this.#c(t,e)}setConfig(e){let t=Ie(e),n=this._config?.entity!==t.entity;this._config=t,n&&(this._lookup={status:"pending"},this.#a())}getCardSize(){return this._config?.layout==="round"?3:1}getGridOptions(){return Rt[this._config?.layout??"pill"]}async getUpdateComplete(){let e=await super.getUpdateComplete();for(;this.#t.size>0;)await Promise.allSettled([...this.#t]),e=await super.getUpdateComplete();return e}#c(e,t){let n=e!==void 0&&t.connected&&!e.connected;(e===void 0||e.language!==t.language||n)&&this.#r(De(t));let o=this._config?.entity;o!==void 0&&(e===void 0||e.entities!==t.entities||n||E(t.states[o])&&!E(e.states[o]))&&this.#a()}#r(e){let t=e.finally(()=>this.#t.delete(t));this.#t.add(t)}#a(){if(this.#i){this.#n=!0;return}this.#i=!0,this.#r(this.#l())}async#l(){try{do{this.#n=!1;let e=this._config?.entity;if(this.#e===void 0||e===void 0)return;let t=await Ze(this.#e,e);this.#n||(this._lookup=t)}while(this.#n)}finally{this.#i=!1}}shouldUpdate(e){let t=this._lookup.status==="found"?this._lookup.info:void 0,n=this._config?F(this._config.entity,t):[];return K(e,this.#e,n)}get#u(){return this.renderRoot.querySelector("timerify-card-popup")}#m(e,t){if(this._lookup.status!=="not_found")return;let n=e.states[t.entity];return n===void 0?f(e,"card_entity_not_found",{entity:t.entity}):E(n)?f(e,"card_not_a_timer",{entity:t.entity}):void 0}render(){let e=this.#e,t=this._config;if(!e||!t)return h;let n=this.#m(e,t);if(n)return this.#s=void 0,m`
        <ha-card>
          <div class="warning" role="alert">
            <ha-icon icon="mdi:alert-outline"></ha-icon>
            <span>${n}</span>
          </div>
        </ha-card>
      `;let o=Date.now(),s=Je(e,t,this._lookup,o);return this.#s=s,m`
      ${Xe(s,t,e,this.#d,this.#h,o)}
      ${this._lookup.status==="found"?m`
            <timerify-card-popup
              .hass=${e}
              .config=${t}
              .info=${this._lookup.info}
              .view=${s}
              @closed=${()=>this.renderRoot.querySelector(".body")?.focus()}
            ></timerify-card-popup>
          `:h}
    `}};if(!customElements.get(he)){customElements.define("timerify-card-popup",q),customElements.define(he,ce);let i={type:he,name:"Timerify",description:f(void 0,"card_picker_description"),preview:!0,documentationURL:"https://github.com/klimofey/timerify#dashboard-card"};(window.customCards??=[]).push(i),Ne(()=>{i.description=f(z(),"card_picker_description")})}export{ce as TimerifyCard};
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
