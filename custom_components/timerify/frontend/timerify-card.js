var G=globalThis,Y=G.ShadowRoot&&(G.ShadyCSS===void 0||G.ShadyCSS.nativeShadow)&&"adoptedStyleSheets"in Document.prototype&&"replace"in CSSStyleSheet.prototype,ae=Symbol(),Te=new WeakMap,O=class{constructor(e,t,n){if(this._$cssResult$=!0,n!==ae)throw Error("CSSResult is not constructable. Use `unsafeCSS` or `css` instead.");this.cssText=e,this.t=t}get styleSheet(){let e=this.o,t=this.t;if(Y&&e===void 0){let n=t!==void 0&&t.length===1;n&&(e=Te.get(t)),e===void 0&&((this.o=e=new CSSStyleSheet).replaceSync(this.cssText),n&&Te.set(t,e))}return e}toString(){return this.cssText}},Se=i=>new O(typeof i=="string"?i:i+"",void 0,ae),y=(i,...e)=>{let t=i.length===1?i[0]:e.reduce((n,o,s)=>n+(r=>{if(r._$cssResult$===!0)return r.cssText;if(typeof r=="number")return r;throw Error("Value passed to 'css' function must be a 'css' function result: "+r+". Use 'unsafeCSS' to pass non-literal values, but take care to ensure page security.")})(o)+i[s+1],i[0]);return new O(t,i,ae)},Ee=(i,e)=>{if(Y)i.adoptedStyleSheets=e.map(t=>t instanceof CSSStyleSheet?t:t.styleSheet);else for(let t of e){let n=document.createElement("style"),o=G.litNonce;o!==void 0&&n.setAttribute("nonce",o),n.textContent=t.cssText,i.appendChild(n)}},de=Y?i=>i:i=>i instanceof CSSStyleSheet?(e=>{let t="";for(let n of e.cssRules)t+=n.cssText;return Se(t)})(i):i;var{is:Et,defineProperty:Ct,getOwnPropertyDescriptor:Pt,getOwnPropertyNames:Ht,getOwnPropertySymbols:Rt,getPrototypeOf:Mt}=Object,X=globalThis,Ce=X.trustedTypes,Ot=Ce?Ce.emptyScript:"",It=X.reactiveElementPolyfillSupport,I=(i,e)=>i,le={toAttribute(i,e){switch(e){case Boolean:i=i?Ot:null;break;case Object:case Array:i=i==null?i:JSON.stringify(i)}return i},fromAttribute(i,e){let t=i;switch(e){case Boolean:t=i!==null;break;case Number:t=i===null?null:Number(i);break;case Object:case Array:try{t=JSON.parse(i)}catch{t=null}}return t}},He=(i,e)=>!Et(i,e),Pe={attribute:!0,type:String,converter:le,reflect:!1,useDefault:!1,hasChanged:He};Symbol.metadata??=Symbol("metadata"),X.litPropertyMetadata??=new WeakMap;var w=class extends HTMLElement{static addInitializer(e){this._$Ei(),(this.l??=[]).push(e)}static get observedAttributes(){return this.finalize(),this._$Eh&&[...this._$Eh.keys()]}static createProperty(e,t=Pe){if(t.state&&(t.attribute=!1),this._$Ei(),this.prototype.hasOwnProperty(e)&&((t=Object.create(t)).wrapped=!0),this.elementProperties.set(e,t),!t.noAccessor){let n=Symbol(),o=this.getPropertyDescriptor(e,n,t);o!==void 0&&Ct(this.prototype,e,o)}}static getPropertyDescriptor(e,t,n){let{get:o,set:s}=Pt(this.prototype,e)??{get(){return this[t]},set(r){this[t]=r}};return{get:o,set(r){let d=o?.call(this);s?.call(this,r),this.requestUpdate(e,d,n)},configurable:!0,enumerable:!0}}static getPropertyOptions(e){return this.elementProperties.get(e)??Pe}static _$Ei(){if(this.hasOwnProperty(I("elementProperties")))return;let e=Mt(this);e.finalize(),e.l!==void 0&&(this.l=[...e.l]),this.elementProperties=new Map(e.elementProperties)}static finalize(){if(this.hasOwnProperty(I("finalized")))return;if(this.finalized=!0,this._$Ei(),this.hasOwnProperty(I("properties"))){let t=this.properties,n=[...Ht(t),...Rt(t)];for(let o of n)this.createProperty(o,t[o])}let e=this[Symbol.metadata];if(e!==null){let t=litPropertyMetadata.get(e);if(t!==void 0)for(let[n,o]of t)this.elementProperties.set(n,o)}this._$Eh=new Map;for(let[t,n]of this.elementProperties){let o=this._$Eu(t,n);o!==void 0&&this._$Eh.set(o,t)}this.elementStyles=this.finalizeStyles(this.styles)}static finalizeStyles(e){let t=[];if(Array.isArray(e)){let n=new Set(e.flat(1/0).reverse());for(let o of n)t.unshift(de(o))}else e!==void 0&&t.push(de(e));return t}static _$Eu(e,t){let n=t.attribute;return n===!1?void 0:typeof n=="string"?n:typeof e=="string"?e.toLowerCase():void 0}constructor(){super(),this._$Ep=void 0,this.isUpdatePending=!1,this.hasUpdated=!1,this._$Em=null,this._$Ev()}_$Ev(){this._$ES=new Promise(e=>this.enableUpdating=e),this._$AL=new Map,this._$E_(),this.requestUpdate(),this.constructor.l?.forEach(e=>e(this))}addController(e){(this._$EO??=new Set).add(e),this.renderRoot!==void 0&&this.isConnected&&e.hostConnected?.()}removeController(e){this._$EO?.delete(e)}_$E_(){let e=new Map,t=this.constructor.elementProperties;for(let n of t.keys())this.hasOwnProperty(n)&&(e.set(n,this[n]),delete this[n]);e.size>0&&(this._$Ep=e)}createRenderRoot(){let e=this.shadowRoot??this.attachShadow(this.constructor.shadowRootOptions);return Ee(e,this.constructor.elementStyles),e}connectedCallback(){this.renderRoot??=this.createRenderRoot(),this.enableUpdating(!0),this._$EO?.forEach(e=>e.hostConnected?.())}enableUpdating(e){}disconnectedCallback(){this._$EO?.forEach(e=>e.hostDisconnected?.())}attributeChangedCallback(e,t,n){this._$AK(e,n)}_$ET(e,t){let n=this.constructor.elementProperties.get(e),o=this.constructor._$Eu(e,n);if(o!==void 0&&n.reflect===!0){let s=(n.converter?.toAttribute!==void 0?n.converter:le).toAttribute(t,n.type);this._$Em=e,s==null?this.removeAttribute(o):this.setAttribute(o,s),this._$Em=null}}_$AK(e,t){let n=this.constructor,o=n._$Eh.get(e);if(o!==void 0&&this._$Em!==o){let s=n.getPropertyOptions(o),r=typeof s.converter=="function"?{fromAttribute:s.converter}:s.converter?.fromAttribute!==void 0?s.converter:le;this._$Em=o;let d=r.fromAttribute(t,s.type);this[o]=d??this._$Ej?.get(o)??d,this._$Em=null}}requestUpdate(e,t,n,o=!1,s){if(e!==void 0){let r=this.constructor;if(o===!1&&(s=this[e]),n??=r.getPropertyOptions(e),!((n.hasChanged??He)(s,t)||n.useDefault&&n.reflect&&s===this._$Ej?.get(e)&&!this.hasAttribute(r._$Eu(e,n))))return;this.C(e,t,n)}this.isUpdatePending===!1&&(this._$ES=this._$EP())}C(e,t,{useDefault:n,reflect:o,wrapped:s},r){n&&!(this._$Ej??=new Map).has(e)&&(this._$Ej.set(e,r??t??this[e]),s!==!0||r!==void 0)||(this._$AL.has(e)||(this.hasUpdated||n||(t=void 0),this._$AL.set(e,t)),o===!0&&this._$Em!==e&&(this._$Eq??=new Set).add(e))}async _$EP(){this.isUpdatePending=!0;try{await this._$ES}catch(t){Promise.reject(t)}let e=this.scheduleUpdate();return e!=null&&await e,!this.isUpdatePending}scheduleUpdate(){return this.performUpdate()}performUpdate(){if(!this.isUpdatePending)return;if(!this.hasUpdated){if(this.renderRoot??=this.createRenderRoot(),this._$Ep){for(let[o,s]of this._$Ep)this[o]=s;this._$Ep=void 0}let n=this.constructor.elementProperties;if(n.size>0)for(let[o,s]of n){let{wrapped:r}=s,d=this[o];r!==!0||this._$AL.has(o)||d===void 0||this.C(o,void 0,s,d)}}let e=!1,t=this._$AL;try{e=this.shouldUpdate(t),e?(this.willUpdate(t),this._$EO?.forEach(n=>n.hostUpdate?.()),this.update(t)):this._$EM()}catch(n){throw e=!1,this._$EM(),n}e&&this._$AE(t)}willUpdate(e){}_$AE(e){this._$EO?.forEach(t=>t.hostUpdated?.()),this.hasUpdated||(this.hasUpdated=!0,this.firstUpdated(e)),this.updated(e)}_$EM(){this._$AL=new Map,this.isUpdatePending=!1}get updateComplete(){return this.getUpdateComplete()}getUpdateComplete(){return this._$ES}shouldUpdate(e){return!0}update(e){this._$Eq&&=this._$Eq.forEach(t=>this._$ET(t,this[t])),this._$EM()}updated(e){}firstUpdated(e){}};w.elementStyles=[],w.shadowRootOptions={mode:"open"},w[I("elementProperties")]=new Map,w[I("finalized")]=new Map,It?.({ReactiveElement:w}),(X.reactiveElementVersions??=[]).push("2.1.2");var ge=globalThis,Re=i=>i,Z=ge.trustedTypes,Me=Z?Z.createPolicy("lit-html",{createHTML:i=>i}):void 0,Le="$lit$",x=`lit$${Math.random().toFixed(9).slice(2)}$`,ze="?"+x,Dt=`<${ze}>`,E=document,N=()=>E.createComment(""),U=i=>i===null||typeof i!="object"&&typeof i!="function",ye=Array.isArray,Nt=i=>ye(i)||typeof i?.[Symbol.iterator]=="function",ce=`[ 	
\f\r]`,D=/<(?:(!--|\/[^a-zA-Z])|(\/?[a-zA-Z][^>\s]*)|(\/?$))/g,Oe=/-->/g,Ie=/>/g,T=RegExp(`>|${ce}(?:([^\\s"'>=/]+)(${ce}*=${ce}*(?:[^ 	
\f\r"'\`<>=]|("|')|))|$)`,"g"),De=/'/g,Ne=/"/g,Ve=/^(?:script|style|textarea|title)$/i,_e=i=>(e,...t)=>({_$litType$:i,strings:e,values:t}),h=_e(1),fn=_e(2),gn=_e(3),$=Symbol.for("lit-noChange"),u=Symbol.for("lit-nothing"),Ue=new WeakMap,S=E.createTreeWalker(E,129);function Be(i,e){if(!ye(i)||!i.hasOwnProperty("raw"))throw Error("invalid template strings array");return Me!==void 0?Me.createHTML(e):e}var Ut=(i,e)=>{let t=i.length-1,n=[],o,s=e===2?"<svg>":e===3?"<math>":"",r=D;for(let d=0;d<t;d++){let a=i[d],m,p,c=-1,f=0;for(;f<a.length&&(r.lastIndex=f,p=r.exec(a),p!==null);)f=r.lastIndex,r===D?p[1]==="!--"?r=Oe:p[1]!==void 0?r=Ie:p[2]!==void 0?(Ve.test(p[2])&&(o=RegExp("</"+p[2],"g")),r=T):p[3]!==void 0&&(r=T):r===T?p[0]===">"?(r=o??D,c=-1):p[1]===void 0?c=-2:(c=r.lastIndex-p[2].length,m=p[1],r=p[3]===void 0?T:p[3]==='"'?Ne:De):r===Ne||r===De?r=T:r===Oe||r===Ie?r=D:(r=T,o=void 0);let g=r===T&&i[d+1].startsWith("/>")?" ":"";s+=r===D?a+Dt:c>=0?(n.push(m),a.slice(0,c)+Le+a.slice(c)+x+g):a+x+(c===-2?d:g)}return[Be(i,s+(i[t]||"<?>")+(e===2?"</svg>":e===3?"</math>":"")),n]},L=class i{constructor({strings:e,_$litType$:t},n){let o;this.parts=[];let s=0,r=0,d=e.length-1,a=this.parts,[m,p]=Ut(e,t);if(this.el=i.createElement(m,n),S.currentNode=this.el.content,t===2||t===3){let c=this.el.content.firstChild;c.replaceWith(...c.childNodes)}for(;(o=S.nextNode())!==null&&a.length<d;){if(o.nodeType===1){if(o.hasAttributes())for(let c of o.getAttributeNames())if(c.endsWith(Le)){let f=p[r++],g=o.getAttribute(c).split(x),A=/([.?@])?(.*)/.exec(f);a.push({type:1,index:s,name:A[2],strings:g,ctor:A[1]==="."?he:A[1]==="?"?me:A[1]==="@"?pe:P}),o.removeAttribute(c)}else c.startsWith(x)&&(a.push({type:6,index:s}),o.removeAttribute(c));if(Ve.test(o.tagName)){let c=o.textContent.split(x),f=c.length-1;if(f>0){o.textContent=Z?Z.emptyScript:"";for(let g=0;g<f;g++)o.append(c[g],N()),S.nextNode(),a.push({type:2,index:++s});o.append(c[f],N())}}}else if(o.nodeType===8)if(o.data===ze)a.push({type:2,index:s});else{let c=-1;for(;(c=o.data.indexOf(x,c+1))!==-1;)a.push({type:7,index:s}),c+=x.length-1}s++}}static createElement(e,t){let n=E.createElement("template");return n.innerHTML=e,n}};function C(i,e,t=i,n){if(e===$)return e;let o=n!==void 0?t._$Co?.[n]:t._$Cl,s=U(e)?void 0:e._$litDirective$;return o?.constructor!==s&&(o?._$AO?.(!1),s===void 0?o=void 0:(o=new s(i),o._$AT(i,t,n)),n!==void 0?(t._$Co??=[])[n]=o:t._$Cl=o),o!==void 0&&(e=C(i,o._$AS(i,e.values),o,n)),e}var ue=class{constructor(e,t){this._$AV=[],this._$AN=void 0,this._$AD=e,this._$AM=t}get parentNode(){return this._$AM.parentNode}get _$AU(){return this._$AM._$AU}u(e){let{el:{content:t},parts:n}=this._$AD,o=(e?.creationScope??E).importNode(t,!0);S.currentNode=o;let s=S.nextNode(),r=0,d=0,a=n[0];for(;a!==void 0;){if(r===a.index){let m;a.type===2?m=new z(s,s.nextSibling,this,e):a.type===1?m=new a.ctor(s,a.name,a.strings,this,e):a.type===6&&(m=new fe(s,this,e)),this._$AV.push(m),a=n[++d]}r!==a?.index&&(s=S.nextNode(),r++)}return S.currentNode=E,o}p(e){let t=0;for(let n of this._$AV)n!==void 0&&(n.strings!==void 0?(n._$AI(e,n,t),t+=n.strings.length-2):n._$AI(e[t])),t++}},z=class i{get _$AU(){return this._$AM?._$AU??this._$Cv}constructor(e,t,n,o){this.type=2,this._$AH=u,this._$AN=void 0,this._$AA=e,this._$AB=t,this._$AM=n,this.options=o,this._$Cv=o?.isConnected??!0}get parentNode(){let e=this._$AA.parentNode,t=this._$AM;return t!==void 0&&e?.nodeType===11&&(e=t.parentNode),e}get startNode(){return this._$AA}get endNode(){return this._$AB}_$AI(e,t=this){e=C(this,e,t),U(e)?e===u||e==null||e===""?(this._$AH!==u&&this._$AR(),this._$AH=u):e!==this._$AH&&e!==$&&this._(e):e._$litType$!==void 0?this.$(e):e.nodeType!==void 0?this.T(e):Nt(e)?this.k(e):this._(e)}O(e){return this._$AA.parentNode.insertBefore(e,this._$AB)}T(e){this._$AH!==e&&(this._$AR(),this._$AH=this.O(e))}_(e){this._$AH!==u&&U(this._$AH)?this._$AA.nextSibling.data=e:this.T(E.createTextNode(e)),this._$AH=e}$(e){let{values:t,_$litType$:n}=e,o=typeof n=="number"?this._$AC(e):(n.el===void 0&&(n.el=L.createElement(Be(n.h,n.h[0]),this.options)),n);if(this._$AH?._$AD===o)this._$AH.p(t);else{let s=new ue(o,this),r=s.u(this.options);s.p(t),this.T(r),this._$AH=s}}_$AC(e){let t=Ue.get(e.strings);return t===void 0&&Ue.set(e.strings,t=new L(e)),t}k(e){ye(this._$AH)||(this._$AH=[],this._$AR());let t=this._$AH,n,o=0;for(let s of e)o===t.length?t.push(n=new i(this.O(N()),this.O(N()),this,this.options)):n=t[o],n._$AI(s),o++;o<t.length&&(this._$AR(n&&n._$AB.nextSibling,o),t.length=o)}_$AR(e=this._$AA.nextSibling,t){for(this._$AP?.(!1,!0,t);e!==this._$AB;){let n=Re(e).nextSibling;Re(e).remove(),e=n}}setConnected(e){this._$AM===void 0&&(this._$Cv=e,this._$AP?.(e))}},P=class{get tagName(){return this.element.tagName}get _$AU(){return this._$AM._$AU}constructor(e,t,n,o,s){this.type=1,this._$AH=u,this._$AN=void 0,this.element=e,this.name=t,this._$AM=o,this.options=s,n.length>2||n[0]!==""||n[1]!==""?(this._$AH=Array(n.length-1).fill(new String),this.strings=n):this._$AH=u}_$AI(e,t=this,n,o){let s=this.strings,r=!1;if(s===void 0)e=C(this,e,t,0),r=!U(e)||e!==this._$AH&&e!==$,r&&(this._$AH=e);else{let d=e,a,m;for(e=s[0],a=0;a<s.length-1;a++)m=C(this,d[n+a],t,a),m===$&&(m=this._$AH[a]),r||=!U(m)||m!==this._$AH[a],m===u?e=u:e!==u&&(e+=(m??"")+s[a+1]),this._$AH[a]=m}r&&!o&&this.j(e)}j(e){e===u?this.element.removeAttribute(this.name):this.element.setAttribute(this.name,e??"")}},he=class extends P{constructor(){super(...arguments),this.type=3}j(e){this.element[this.name]=e===u?void 0:e}},me=class extends P{constructor(){super(...arguments),this.type=4}j(e){this.element.toggleAttribute(this.name,!!e&&e!==u)}},pe=class extends P{constructor(e,t,n,o,s){super(e,t,n,o,s),this.type=5}_$AI(e,t=this){if((e=C(this,e,t,0)??u)===$)return;let n=this._$AH,o=e===u&&n!==u||e.capture!==n.capture||e.once!==n.once||e.passive!==n.passive,s=e!==u&&(n===u||o);o&&this.element.removeEventListener(this.name,this,n),s&&this.element.addEventListener(this.name,this,e),this._$AH=e}handleEvent(e){typeof this._$AH=="function"?this._$AH.call(this.options?.host??this.element,e):this._$AH.handleEvent(e)}},fe=class{constructor(e,t,n){this.element=e,this.type=6,this._$AN=void 0,this._$AM=t,this.options=n}get _$AU(){return this._$AM._$AU}_$AI(e){C(this,e)}};var Lt=ge.litHtmlPolyfillSupport;Lt?.(L,z),(ge.litHtmlVersions??=[]).push("3.3.3");var We=(i,e,t)=>{let n=t?.renderBefore??e,o=n._$litPart$;if(o===void 0){let s=t?.renderBefore??null;n._$litPart$=o=new z(e.insertBefore(N(),s),s,void 0,t??{})}return o._$AI(i),o};var ve=globalThis,v=class extends w{constructor(){super(...arguments),this.renderOptions={host:this},this._$Do=void 0}createRenderRoot(){let e=super.createRenderRoot();return this.renderOptions.renderBefore??=e.firstChild,e}update(e){let t=this.render();this.hasUpdated||(this.renderOptions.isConnected=this.isConnected),super.update(e),this._$Do=We(t,this.renderRoot,this.renderOptions)}connectedCallback(){super.connectedCallback(),this._$Do?.setConnected(!0)}disconnectedCallback(){super.disconnectedCallback(),this._$Do?.setConnected(!1)}render(){return $}};v._$litElement$=!0,v.finalized=!0,ve.litElementHydrateSupport?.({LitElement:v});var zt=ve.litElementPolyfillSupport;zt?.({LitElement:v});(ve.litElementVersions??=[]).push("4.2.2");async function V(i,e,t,n,o){try{await i.callService(e,t,n,{entity_id:o})}catch{}}function B(i,e,t){return V(i,"number","set_value",{value:t},e)}function W(i,e,t){return V(i,"timerify","add_time",{minutes:t},e)}function je(i,e){return V(i,"timerify","run",{},e)}function Fe(i,e,t){return V(i,"switch",t?"turn_on":"turn_off",{},e)}function Ke(i,e,t){return V(i,"timerify","cancel_command",{command_id:t},e)}var qe={card_entity_not_found:"Entity not found: {entity}",card_not_a_timer:"{entity} is not the Run for number of a Timerify timer",card_timer_incomplete:"The timer of {entity} cannot be shown: its target or one of its sensors is missing. Open the timer's page to see why.",card_not_allowed:"You are not allowed to see the timer {entity}",card_ends_at_disabled:"The Ends at sensor of this timer, {sensor}, is disabled. Enable it for the card to work",card_error_entity:"Choose the Run for number of a timer",card_error_layout:"The layout is pill or round",card_error_presets:"Presets are whole minutes from 1 to 1440",card_error_chip:"The quick chip is whole minutes from 1 to 1440",card_close:"Close",card_until:"until {time}",card_add_time:"Add {duration}",card_subtract_time:"Take off {duration}",card_stop:"Stop",card_schedule:"Schedule",card_commands:"Pending commands",card_commands_disabled:"Pending commands are hidden: the Next command sensor, {sensor}, is disabled",card_command_on:"On at {time}",card_command_on_for:"On at {time} for {duration}",card_command_off:"Off at {time}",card_cancel_command:"Cancel",card_settings:"Settings",card_picker_description:"The countdown, presets and schedule of a Timerify timer",card_editor_entity:"Timer",card_editor_layout:"Layout",card_editor_layout_pill:"Pill",card_editor_layout_round:"Round",card_editor_name:"Name",card_editor_icon:"Icon",card_editor_presets:"Duration presets (minutes)",card_editor_presets_helper:"Leave empty for {presets}",card_editor_chip:"Quick add chip (minutes, pill only)"};var Ye="common",Xe="timerify",Bt=`component.${Xe}.${Ye}.`;function be(i){return Bt+i}function Wt(i,e){return i.replace(/\{(\w+)\}/g,(t,n)=>String(e?.[n]??t))}function l(i,e,t){return i?.localize(be(e),t)||Wt(qe[e],t)}var j,Ge=Promise.resolve(),Ze,Je=new Set;function J(i){return i.language!==j&&(j=i.language,Ge=jt(i,i.language)),Ge}async function jt(i,e){let t;try{t=await i.loadBackendTranslation(Ye,Xe)}catch{j===e&&(j=void 0);return}j===e&&(Ze={...i,localize:t},Je.forEach(n=>n()))}function k(){return Ze}function Qe(i){Je.add(i)}var F=[15,30,45,60,120],we=1440,_=class extends Error{constructor(t){super(l(k(),t));this.key=t}key};function tt(i){let e=typeof i=="number"?i:typeof i=="string"&&/^\d+$/.test(i)?Number(i):void 0;return e!==void 0&&Number.isInteger(e)&&e>=1&&e<=we?e:void 0}function Ft(i){if(i===void 0||Array.isArray(i)&&i.length===0)return[...F];if(!Array.isArray(i))throw new _("card_error_presets");let e=new Set;for(let t of i){let n=tt(t);if(n===void 0)throw new _("card_error_presets");e.add(n)}return[...e]}function Kt(i){if(i===void 0)return;let e=tt(i);if(e===void 0)throw new _("card_error_chip");return e}var nt=i=>typeof i=="object"&&i!==null?i:{},et=i=>typeof i=="number"||typeof i=="string";function it(i){let{entity:e,layout:t,presets:n,chip:o}=nt(i);if(e!==void 0&&typeof e!="string")throw new _("card_error_entity");if(t!==void 0&&typeof t!="string")throw new _("card_error_layout");if(n!==void 0&&!(Array.isArray(n)&&n.every(et)))throw new _("card_error_presets");if(o!==void 0&&!et(o))throw new _("card_error_chip")}function ot(i){let e=nt(i),{entity:t,layout:n="pill",name:o,icon:s}=e;if(typeof t!="string"||!/^number\.[a-z0-9_]+$/.test(t))throw new _("card_error_entity");if(n!=="pill"&&n!=="round")throw new _("card_error_layout");let r=Kt(e.chip);return{entity:t,layout:n,...typeof o=="string"&&o!==""&&{name:o},...typeof s=="string"&&s!==""&&{icon:s},presets:Ft(e.presets),...r!==void 0&&{chip:r}}}var Q=class{#e;#i;#t=!1;#n;constructor(e,t){this.#e=e,this.#i=t,e.addController(this)}hostConnected(){this.#t=!0,this.#o()}hostUpdated(){this.#o()}hostDisconnected(){this.#t=!1,this.#o()}#o(){let e=this.#i(),t=this.#t&&e!==void 0&&e.getTime()>Date.now();t&&this.#n===void 0?this.#n=setInterval(()=>this.#e.requestUpdate(),1e3):!t&&this.#n!==void 0&&(clearInterval(this.#n),this.#n=void 0)}};var st=i=>String(i).padStart(2,"0");function H(i){let e=Math.ceil(Math.max(0,i)),t=Math.floor(e/3600),n=Math.floor(e%3600/60),o=st(e%60);return t>0?`${t}:${st(n)}:${o}`:`${n}:${o}`}function qt({language:i,time_format:e}){if(e==="12"||e==="24")return e==="12";let t=new Intl.DateTimeFormat(e==="language"?i:void 0,{hour:"numeric"}).resolvedOptions();return t.hourCycle==="h11"||t.hourCycle==="h12"}var Gt=864e5;function rt(i,e){let t=new Intl.DateTimeFormat("en-US",{timeZone:i,year:"numeric",month:"numeric",day:"numeric"}).formatToParts(e),n=o=>Number(t.find(s=>s.type===o)?.value);return Date.UTC(n("year"),n("month")-1,n("day"))/Gt}function K(i,e,t){let{locale:n}=i,o=n.time_zone==="server"?i.config.time_zone:void 0,s=rt(o,e.getTime())-rt(o,t),r=s===0?{}:s>=1&&s<=6?{weekday:"short"}:{month:"short",day:"numeric"};return new Intl.DateTimeFormat(n.language,{...r,hour:"numeric",minute:"2-digit",hourCycle:qt(n)?"h12":"h23",timeZone:o}).format(e)}function b(i,e){let t=(r,d)=>new Intl.NumberFormat(i.locale.language,{style:"unit",unit:d,unitDisplay:"short",useGrouping:!1}).format(r),n=Math.floor(e/60),o=e%60,s=n>0?[t(n,"hour")]:[];return(o>0||n===0)&&s.push(t(o,"minute")),s.join(" ")}function at(i,e,t,n,o){return t.includes(n)&&typeof o=="number"?new Intl.NumberFormat(i.locale.language,{style:"percent",maximumFractionDigits:1}).format(o/100):e===void 0?String(o):n==="hvac_mode"?i.formatEntityState(e,String(o)):i.formatEntityAttributeValue(e,n,o)}var dt={entity:"card_editor_entity",layout:"card_editor_layout",name:"card_editor_name",icon:"card_editor_icon",presets:"card_editor_presets",chip:"card_editor_chip"},Yt=i=>Object.hasOwn(dt,i),Xt={locale:{language:"en"}};function lt(){return k()??Xt}function Zt(){let i=lt();return new Intl.ListFormat(i.locale.language,{style:"long",type:"conjunction"}).format(F.map(e=>b(i,e)))}async function ct(){let i=k();return{schema:[{name:"entity",required:!0,selector:{entity:{filter:{integration:"timerify",domain:"number"}}}},{name:"layout",selector:{select:{options:[{value:"pill",label:l(i,"card_editor_layout_pill")},{value:"round",label:l(i,"card_editor_layout_round")}]}}},{name:"",type:"grid",schema:[{name:"name",selector:{text:{}}},{name:"icon",selector:{icon:{}}}]},{name:"presets",selector:{select:{multiple:!0,custom_value:!0,options:F.map(e=>({value:String(e),label:b(lt(),e)}))}}},{name:"chip",selector:{number:{min:1,max:we,mode:"box"}}}],assertConfig:it,computeLabel:({name:e},t)=>Yt(e)?t(be(dt[e])):"",computeHelper:({name:e})=>e==="presets"?l(k(),"card_editor_presets_helper",{presets:Zt()}):void 0}}function ut(i,e,t){J(i);let n=s=>{let r=i.entities[s];return r?.platform==="timerify"&&r.translation_key==="run_for"},o=s=>s.filter(n).sort()[0];return{entity:o(e)??o(t)??o(Object.keys(i.entities))??"",layout:"pill",presets:F.map(String)}}var Jt="not_found",Qt="timer_incomplete",en="unauthorized";async function pt(i,e){try{return{status:"found",info:await i.callWS({type:"timerify/timer",entity_id:e})}}catch(t){let n=typeof t=="object"&&t!==null&&"code"in t?t.code:"";return n===Jt?{status:"not_found"}:n===Qt?{status:"incomplete"}:{status:n===en?"unauthorized":"failed"}}}var ee=(i,e)=>i.disabled_sensors.includes(e),R=i=>i!==void 0&&i.state!=="unavailable"&&i.state!=="unknown";function tn(i,e){return i===void 0||i.state==="unavailable"||i.state==="unknown"?!1:e.states.includes(i.state)===(e.match==="is")}var nn="mdi:timer-outline",ht=i=>i===void 0||i.state==="unavailable";function mt(i){let e=typeof i=="string"?Date.parse(i):Number.NaN;return Number.isNaN(e)?void 0:e}function ft(i,e,t,n){let o=t.status==="found"?t.info:void 0,s=i.states[e.entity],r=o&&i.states[o.target],d=e.name||r&&i.formatEntityName(r,void 0)||s?.attributes.friendly_name||e.entity,a=e.icon?{icon:e.icon}:r?{stateObj:r}:{icon:nn},m={name:d,icon:a,target:r,remaining:0},p=o&&i.states[o.ends_at];if(o===void 0||p===void 0||ht(s)||ht(p))return{...m,state:"unavailable",progress:0};let c=mt(p.state);if(c===void 0)return tn(r,o.target_on)?{...m,state:"open",progress:1}:{...m,state:"idle",progress:0};let f=mt(p.attributes.started_at),g=f===void 0?0:(c-f)/1e3,A=Math.max(0,(c-n)/1e3);return{...m,state:"counting",remaining:A,progress:g>0?Math.min(1,A/g):1,endsAt:new Date(c)}}function te(i,e){return e?[i,e.ends_at,e.next_command,e.target,...e.intervals.map(({entity_id:t})=>t)]:[i]}var on=["locale","language","localize","config","user","connected","entities","formatEntityName","formatEntityState","formatEntityAttributeValue"];function ne(i,e,t){for(let o of i.keys())if(o!=="hass")return!0;let n=i.get("hass");return n===void 0||e===void 0?!0:on.some(o=>n[o]!==e[o])||t.some(o=>n.states[o]!==e.states[o])}function ie(i){return"stateObj"in i.icon?h`<ha-state-icon .stateObj=${i.icon.stateObj}></ha-state-icon>`:h`<ha-icon .icon=${i.icon.icon}></ha-icon>`}function sn(i,e,t){if(i.state!=="unavailable")return i.target?t.formatEntityState(i.target):"";let n=t.states[e.entity];if(R(n))return"";let o={entity_id:e.entity,state:"unavailable",attributes:{}};return t.formatEntityState(n??o,"unavailable")}function oe(i,e,t,n){if(i.state!=="counting"||i.endsAt===void 0)return sn(i,e,t);let o=K(t,i.endsAt,n);return h`
    <span class="remaining">${H(i.remaining)}</span>
    <span class="until">${l(t,"card_until",{time:o})}</span>
  `}var gt=y`
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
`;var yt={ATTRIBUTE:1,CHILD:2,PROPERTY:3,BOOLEAN_ATTRIBUTE:4,EVENT:5,ELEMENT:6},_t=i=>(...e)=>({_$litDirective$:i,values:e}),se=class{constructor(e){}get _$AU(){return this._$AM._$AU}_$AT(e,t,n){this._$Ct=e,this._$AM=t,this._$Ci=n}_$AS(e,t){return this.update(e,t)}update(e,t){return this.render(...t)}};var vt="important",rn=" !"+vt,bt=_t(class extends se{constructor(i){if(super(i),i.type!==yt.ATTRIBUTE||i.name!=="style"||i.strings?.length>2)throw Error("The `styleMap` directive must be used in the `style` attribute and must be the only part in the attribute.")}render(i){return Object.keys(i).reduce((e,t)=>{let n=i[t];return n==null?e:e+`${t=t.includes("-")?t:t.replace(/(?:^(webkit|moz|ms|o)|)(?=[A-Z])/g,"-$&").toLowerCase()}:${n};`},"")}update(i,[e]){let{style:t}=i.element;if(this.ft===void 0)return this.ft=new Set(Object.keys(e)),this.render(e);for(let n of this.ft)e[n]==null&&(this.ft.delete(n),n.includes("-")?t.removeProperty(n):t[n]=null);for(let n in e){let o=e[n];if(o!=null){this.ft.add(n);let s=typeof o=="string"&&o.endsWith(rn);n.includes("-")||s?t.setProperty(n,s?o.slice(0,-11):o,s?vt:""):t[n]=o}}return $}});function wt(i,e,t,n,o,s){let r=Math.round(i.progress*1e3)/10;return h`
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
          <span class="fill" style=${bt({width:`${r}%`})}></span>
        </span>
      </div>
      <div class="content">
        <span class="icon">${ie(i)}</span>
        <span class="text" id="label">
          <span class="name">${i.name}</span>
          <span class="status">${oe(i,e,t,s)}</span>
        </span>
        ${e.chip===void 0?u:h`
              <button
                class="chip"
                type="button"
                aria-label=${l(t,"card_add_time",{duration:b(t,e.chip)})}
                ?disabled=${i.state==="unavailable"}
                @click=${o}
              >
                +${b(t,e.chip)}
              </button>
            `}
      </div>
    </ha-card>
  `}var $t=y`
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
  .chip:disabled {
    color: var(--disabled-text-color);
    cursor: default;
  }
  .chip:focus-visible {
    outline: 2px solid var(--primary-color);
    outline-offset: 2px;
  }
`;function an(i){let e=i?.attributes.commands;return Array.isArray(e)?e.flatMap(t=>{if(typeof t!="object"||t===null)return[];let{id:n,at:o,action:s,minutes:r,settings:d}=t,a=typeof o=="string"?new Date(o):void 0;return typeof n!="string"||a===void 0||Number.isNaN(a.getTime())||s!=="on"&&s!=="off"?[]:[{id:n,at:a,action:s,minutes:typeof r=="number"&&r>0?r:null,settings:typeof d=="object"&&d!==null?Object.entries(d):[]}]}):[]}var dn=i=>`/config/integrations/integration/timerify#config_entry=${encodeURIComponent(i)}`,re=class extends v{static properties={hass:{attribute:!1},config:{attribute:!1},info:{attribute:!1},view:{attribute:!1},opened:{state:!0}};static styles=y`
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
    .settings,
    .note {
      color: var(--secondary-text-color);
      font-size: var(--ha-font-size-s, 12px);
    }
    .note {
      margin: 0;
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
  `;constructor(){super(),this.opened=!1}open(){this.opened=!0}close(){this.#e?.close(),this.#r()}disconnectedCallback(){super.disconnectedCallback(),this.close()}get#e(){return this.renderRoot.querySelector("dialog")}#i=()=>{this.#e?.open||this.#r()};#t=!1;#n=e=>{this.#t=e.target===e.currentTarget};#o=e=>{this.#t&&=e.target===e.currentTarget};#d=()=>{this.#t=!1};#s=e=>{let t=this.#t&&e.target===e.currentTarget;this.#t=!1,t&&this.close()};#r(){this.opened&&(this.opened=!1,this.dispatchEvent(new CustomEvent("closed")))}shouldUpdate(e){if(!this.hasUpdated||e.has("opened"))return!0;let t=te(this.config.entity,this.info);return this.opened&&ne(e,this.hass,t)}updated(e){let t=this.#e;e.has("opened")&&this.opened&&t&&!t.open&&t.showModal()}render(){return h`
      <dialog
        aria-labelledby="title"
        @cancel=${()=>this.close()}
        @close=${this.#i}
        @pointerdown=${this.#n}
        @pointerup=${this.#o}
        @pointercancel=${this.#d}
        @click=${this.#s}
      >
        ${this.opened?this.#l():u}
      </dialog>
    `}#l(){let{hass:e,view:t}=this,n=Date.now();return h`
      <div class="wrapper">
        <header>
          <h2 id="title">${t.name}</h2>
          <button class="close" @click=${()=>this.close()}>${l(e,"card_close")}</button>
        </header>
        ${this.#a(n)} ${this.#c()} ${this.#h()} ${this.#m(n)}
        ${this.#f()}
      </div>
    `}#a(e){let{hass:t,view:n}=this;if(n.state!=="counting"||n.endsAt===void 0)return u;let o=K(t,n.endsAt,e);return h`
      <p class="countdown">
        <span class="remaining">${H(n.remaining)}</span>
        <span class="until">${l(t,"card_until",{time:o})}</span>
      </p>
    `}#c(){let{hass:e,config:t,view:n}=this,o=b(e,5),s=n.state==="counting",r=s||n.state==="open",d=n.state==="unavailable";return h`
      <div class="presets">
        ${t.presets.map(a=>h`
            <button
              class="action preset"
              ?disabled=${d}
              @click=${()=>{B(e,t.entity,a)}}
            >
              ${b(e,a)}
            </button>
          `)}
      </div>
      <div class="adjust">
        <button
          class="action step"
          aria-label=${l(e,"card_subtract_time",{duration:o})}
          ?disabled=${!s}
          @click=${()=>{W(e,t.entity,-5)}}
        >
          −${o}
        </button>
        <button
          class="action step"
          aria-label=${l(e,"card_add_time",{duration:o})}
          ?disabled=${d}
          @click=${()=>{W(e,t.entity,5)}}
        >
          +${o}
        </button>
        <button
          class="action stop"
          ?disabled=${!r}
          @click=${()=>{B(e,t.entity,0)}}
        >
          ${l(e,"card_stop")}
        </button>
      </div>
    `}#h(){let{intervals:e}=this.info;return e.length===0?u:h`
      <section class="schedule">
        <h3>${l(this.hass,"card_schedule")}</h3>
        <ul>
          ${e.map(t=>h`<li>${this.#u(t)}</li>`)}
        </ul>
      </section>
    `}#u({entity_id:e,title:t}){let{hass:n}=this,o=n.states[e],s=o!==void 0&&o.state!=="unavailable",r=s&&o.state==="on",d=o??{entity_id:e,state:"unavailable",attributes:{}};return h`
      <button
        class="interval"
        role="switch"
        aria-checked=${r?"true":"false"}
        ?disabled=${!s}
        @click=${()=>{Fe(n,e,!r)}}
      >
        <span class="label">
          <span class="title">${t}</span>
          ${s?u:h`<span class="state">${n.formatEntityState(d,"unavailable")}</span>`}
        </span>
        <span class="track" aria-hidden="true"><span class="knob"></span></span>
      </button>
    `}#m(e){let{hass:t,config:n,info:o,view:s}=this;if(ee(o,o.next_command))return h`
        <section class="commands">
          <p class="note">${l(t,"card_commands_disabled",{sensor:o.next_command})}</p>
        </section>
      `;let r=an(t.states[o.next_command]);if(r.length===0)return u;let d=s.state==="unavailable";return h`
      <section class="commands">
        <h3>${l(t,"card_commands")}</h3>
        <ul>
          ${r.map((a,m)=>{let p=a.settings.map(([c,f])=>at(t,s.target,o.percent_settings,c,f));return h`
              <li>
                <div class="command" id="command-${m}">
                  <span class="what">${this.#p(a,e)}</span>
                  ${p.length===0?u:h`<span class="settings">${p.join(", ")}</span>`}
                </div>
                <button
                  class="cancel"
                  aria-label=${l(t,"card_cancel_command")}
                  aria-describedby="command-${m}"
                  ?disabled=${d}
                  @click=${()=>{Ke(t,n.entity,a.id)}}
                >
                  <span aria-hidden="true">×</span>
                </button>
              </li>
            `})}
        </ul>
      </section>
    `}#p(e,t){let{hass:n}=this,o=K(n,e.at,t);return e.action==="off"?l(n,"card_command_off",{time:o}):e.minutes===null?l(n,"card_command_on",{time:o}):l(n,"card_command_on_for",{time:o,duration:b(n,e.minutes)})}#f(){return this.hass.user?.is_admin?h`
      <footer>
        <a href=${dn(this.info.entry_id)} @click=${this.#g}>
          ${l(this.hass,"card_settings")}
        </a>
      </footer>
    `:u}#g=e=>{!e.ctrlKey&&!e.metaKey&&!e.shiftKey&&this.close()}};var xt="data-held",q=class{#e;#i;#t=!1;#n;#o;#d=!1;#s=!1;constructor(e,t){this.#e=e,this.#i=t,e.addController(this)}hostDisconnected(){this.#t=!1,this.#s=!1,this.#a()}binding(){let e={click:n=>{if(this.#s){this.#s=!1,n.preventDefault(),n.stopPropagation();return}this.#i.tap()},keydown:n=>{n.key==="Enter"?(n.preventDefault(),n.repeat||this.#i.tap()):n.key===" "&&(n.preventDefault(),this.#t=!0)},keyup:n=>{if(n.key!==" ")return;let o=this.#t;this.#t=!1,o&&this.#i.tap()}},{hold:t}=this.#i;return t===void 0?e:{...e,pointerdown:n=>this.#r(n),pointerup:n=>{if(n.pointerId!==this.#n)return;let o=this.#d;this.#a(),o&&(this.#s=!0,t())},pointercancel:n=>this.#l(n),pointerleave:n=>this.#l(n),contextmenu:n=>{this.#n!==void 0&&n.preventDefault()}}}#r(e){!e.isPrimary||e.button!==0||(this.#s=!1,this.#a(),this.#n=e.pointerId,this.#o=setTimeout(()=>{this.#o=void 0,this.#d=!0,this.#e.setAttribute(xt,"")},500))}#l(e){e.pointerId===this.#n&&this.#a()}#a(){clearTimeout(this.#o),this.#o=void 0,this.#n=void 0,this.#d=!1,this.#e.removeAttribute(xt)}};var M=80,At=6,xe=(M-At)/2,kt=2*Math.PI*xe;function ln(i){if(i.state!=="counting")return h`<span class="icon">${ie(i)}</span>`;let e=H(i.remaining);return h`<span class="time" aria-hidden="true">${e}</span>`}function Tt(i,e,t,n,o){let s=M/2;return h`
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
          <svg class="ring" viewBox="0 0 ${M} ${M}" aria-hidden="true">
            <circle class="track" cx=${s} cy=${s} r=${xe}></circle>
            <circle
              class="progress"
              cx=${s}
              cy=${s}
              r=${xe}
              transform="rotate(-90 ${s} ${s})"
              stroke-dasharray=${kt}
              stroke-dashoffset=${(1-i.progress)*kt}
            ></circle>
          </svg>
          <span class="centre">
            ${ln(i)}
          </span>
        </div>
        <span class="text" id="label">
          <span class="name">${i.name}</span>
          <span class="status">${oe(i,e,t,o)}</span>
        </span>
      </div>
    </ha-card>
  `}var St=y`
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
    width: ${M}px;
    height: ${M}px;
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
    stroke-width: ${At};
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
`;var ke="timerify-card",cn={pill:{columns:6,rows:1,min_columns:3,min_rows:1,max_rows:1},round:{columns:3,rows:2,min_columns:2,min_rows:2,max_rows:3}},Ae=class extends v{static properties={hass:{attribute:!1,noAccessor:!0},_config:{state:!0},_lookup:{state:!0}};static styles=[gt,$t,St,y`
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
    `];static getConfigForm=ct;static getStubConfig=ut;#e;#i=new Set;#t=!1;#n=!1;#o=new q(this,{tap:()=>this.#u?.open()}).binding();#d=new q(this,{tap:()=>this.#u?.open(),hold:()=>this.#m()}).binding();#s=()=>{let{_config:e,hass:t}=this;e?.chip!==void 0&&t!==void 0&&W(t,e.entity,e.chip)};#r;constructor(){super(),this._lookup={status:"pending"},new Q(this,()=>this.#r?.endsAt)}get hass(){return this.#e}set hass(e){let t=this.#e;this.#e=e,this.requestUpdate("hass",t),this.#l(t,e)}setConfig(e){let t=ot(e),n=this._config?.entity!==t.entity;this._config=t,n&&(this._lookup={status:"pending"},this.#c())}getCardSize(){return this._config?.layout==="round"?3:1}getGridOptions(){return cn[this._config?.layout??"pill"]}async getUpdateComplete(){let e=await super.getUpdateComplete();for(;this.#i.size>0;)await Promise.allSettled([...this.#i]),e=await super.getUpdateComplete();return e}#l(e,t){let n=e!==void 0&&t.connected&&!e.connected;(e===void 0||e.language!==t.language||n)&&this.#a(J(t));let o=this._config?.entity;o!==void 0&&(e===void 0||e.entities!==t.entities||n||R(t.states[o])&&!R(e.states[o]))&&this.#c()}#a(e){let t=e.finally(()=>this.#i.delete(t));this.#i.add(t)}#c(){if(this.#t){this.#n=!0;return}this.#t=!0,this.#a(this.#h())}async#h(){try{do{this.#n=!1;let e=this._config?.entity;if(this.#e===void 0||e===void 0)return;let t=await pt(this.#e,e);this.#n||(this._lookup=t)}while(this.#n)}finally{this.#t=!1}}shouldUpdate(e){let t=this._lookup.status==="found"?this._lookup.info:void 0,n=this._config?te(this._config.entity,t):[];return ne(e,this.#e,n)}get#u(){return this.renderRoot.querySelector("timerify-card-popup")}#m(){let{_config:e,hass:t}=this,n=this.#r?.state;e===void 0||t===void 0||(n==="counting"||n==="open"?B(t,e.entity,0):n==="idle"&&je(t,e.entity))}#p(e,t){let n=this._lookup;if(n.status==="unauthorized")return l(e,"card_not_allowed",{entity:t.entity});if(n.status==="incomplete")return l(e,"card_timer_incomplete",{entity:t.entity});if(n.status==="found"&&ee(n.info,n.info.ends_at))return l(e,"card_ends_at_disabled",{sensor:n.info.ends_at});if(n.status!=="not_found")return;let o=e.states[t.entity];return o===void 0?l(e,"card_entity_not_found",{entity:t.entity}):R(o)?l(e,"card_not_a_timer",{entity:t.entity}):void 0}render(){let e=this.#e,t=this._config;if(!e||!t)return u;let n=this.#p(e,t);if(n)return this.#r=void 0,h`
        <ha-card>
          <div class="warning" role="alert">
            <ha-icon icon="mdi:alert-outline"></ha-icon>
            <span>${n}</span>
          </div>
        </ha-card>
      `;let o=Date.now(),s=ft(e,t,this._lookup,o);return this.#r=s,h`
      ${t.layout==="round"?Tt(s,t,e,this.#d,o):wt(s,t,e,this.#o,this.#s,o)}
      ${this._lookup.status==="found"?h`
            <timerify-card-popup
              .hass=${e}
              .config=${t}
              .info=${this._lookup.info}
              .view=${s}
              @closed=${()=>this.renderRoot.querySelector(".body")?.focus()}
            ></timerify-card-popup>
          `:u}
    `}};if(!customElements.get(ke)){customElements.define("timerify-card-popup",re),customElements.define(ke,Ae);let i={type:ke,name:"Timerify",description:l(void 0,"card_picker_description"),preview:!0,documentationURL:"https://github.com/klimofey/timerify#dashboard-card"};(window.customCards??=[]).push(i),Qe(()=>{i.description=l(k(),"card_picker_description")})}export{Ae as TimerifyCard};
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
