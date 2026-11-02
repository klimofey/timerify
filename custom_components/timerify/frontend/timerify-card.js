var Y=globalThis,X=Y.ShadowRoot&&(Y.ShadyCSS===void 0||Y.ShadyCSS.nativeShadow)&&"adoptedStyleSheets"in Document.prototype&&"replace"in CSSStyleSheet.prototype,lt=Symbol(),Ct=new WeakMap,O=class{constructor(t,e,n){if(this._$cssResult$=!0,n!==lt)throw Error("CSSResult is not constructable. Use `unsafeCSS` or `css` instead.");this.cssText=t,this.t=e}get styleSheet(){let t=this.o,e=this.t;if(X&&t===void 0){let n=e!==void 0&&e.length===1;n&&(t=Ct.get(e)),t===void 0&&((this.o=t=new CSSStyleSheet).replaceSync(this.cssText),n&&Ct.set(e,t))}return t}toString(){return this.cssText}},Tt=i=>new O(typeof i=="string"?i:i+"",void 0,lt),y=(i,...t)=>{let e=i.length===1?i[0]:t.reduce((n,o,s)=>n+(r=>{if(r._$cssResult$===!0)return r.cssText;if(typeof r=="number")return r;throw Error("Value passed to 'css' function must be a 'css' function result: "+r+". Use 'unsafeCSS' to pass non-literal values, but take care to ensure page security.")})(o)+i[s+1],i[0]);return new O(e,i,lt)},Pt=(i,t)=>{if(X)i.adoptedStyleSheets=t.map(e=>e instanceof CSSStyleSheet?e:e.styleSheet);else for(let e of t){let n=document.createElement("style"),o=Y.litNonce;o!==void 0&&n.setAttribute("nonce",o),n.textContent=e.cssText,i.appendChild(n)}},dt=X?i=>i:i=>i instanceof CSSStyleSheet?(t=>{let e="";for(let n of t.cssRules)e+=n.cssText;return Tt(e)})(i):i;var{is:Te,defineProperty:Pe,getOwnPropertyDescriptor:He,getOwnPropertyNames:Re,getOwnPropertySymbols:Me,getPrototypeOf:Oe}=Object,Z=globalThis,Ht=Z.trustedTypes,Ne=Ht?Ht.emptyScript:"",Ue=Z.reactiveElementPolyfillSupport,N=(i,t)=>i,ct={toAttribute(i,t){switch(t){case Boolean:i=i?Ne:null;break;case Object:case Array:i=i==null?i:JSON.stringify(i)}return i},fromAttribute(i,t){let e=i;switch(t){case Boolean:e=i!==null;break;case Number:e=i===null?null:Number(i);break;case Object:case Array:try{e=JSON.parse(i)}catch{e=null}}return e}},Mt=(i,t)=>!Te(i,t),Rt={attribute:!0,type:String,converter:ct,reflect:!1,useDefault:!1,hasChanged:Mt};Symbol.metadata??=Symbol("metadata"),Z.litPropertyMetadata??=new WeakMap;var $=class extends HTMLElement{static addInitializer(t){this._$Ei(),(this.l??=[]).push(t)}static get observedAttributes(){return this.finalize(),this._$Eh&&[...this._$Eh.keys()]}static createProperty(t,e=Rt){if(e.state&&(e.attribute=!1),this._$Ei(),this.prototype.hasOwnProperty(t)&&((e=Object.create(e)).wrapped=!0),this.elementProperties.set(t,e),!e.noAccessor){let n=Symbol(),o=this.getPropertyDescriptor(t,n,e);o!==void 0&&Pe(this.prototype,t,o)}}static getPropertyDescriptor(t,e,n){let{get:o,set:s}=He(this.prototype,t)??{get(){return this[e]},set(r){this[e]=r}};return{get:o,set(r){let l=o?.call(this);s?.call(this,r),this.requestUpdate(t,l,n)},configurable:!0,enumerable:!0}}static getPropertyOptions(t){return this.elementProperties.get(t)??Rt}static _$Ei(){if(this.hasOwnProperty(N("elementProperties")))return;let t=Oe(this);t.finalize(),t.l!==void 0&&(this.l=[...t.l]),this.elementProperties=new Map(t.elementProperties)}static finalize(){if(this.hasOwnProperty(N("finalized")))return;if(this.finalized=!0,this._$Ei(),this.hasOwnProperty(N("properties"))){let e=this.properties,n=[...Re(e),...Me(e)];for(let o of n)this.createProperty(o,e[o])}let t=this[Symbol.metadata];if(t!==null){let e=litPropertyMetadata.get(t);if(e!==void 0)for(let[n,o]of e)this.elementProperties.set(n,o)}this._$Eh=new Map;for(let[e,n]of this.elementProperties){let o=this._$Eu(e,n);o!==void 0&&this._$Eh.set(o,e)}this.elementStyles=this.finalizeStyles(this.styles)}static finalizeStyles(t){let e=[];if(Array.isArray(t)){let n=new Set(t.flat(1/0).reverse());for(let o of n)e.unshift(dt(o))}else t!==void 0&&e.push(dt(t));return e}static _$Eu(t,e){let n=e.attribute;return n===!1?void 0:typeof n=="string"?n:typeof t=="string"?t.toLowerCase():void 0}constructor(){super(),this._$Ep=void 0,this.isUpdatePending=!1,this.hasUpdated=!1,this._$Em=null,this._$Ev()}_$Ev(){this._$ES=new Promise(t=>this.enableUpdating=t),this._$AL=new Map,this._$E_(),this.requestUpdate(),this.constructor.l?.forEach(t=>t(this))}addController(t){(this._$EO??=new Set).add(t),this.renderRoot!==void 0&&this.isConnected&&t.hostConnected?.()}removeController(t){this._$EO?.delete(t)}_$E_(){let t=new Map,e=this.constructor.elementProperties;for(let n of e.keys())this.hasOwnProperty(n)&&(t.set(n,this[n]),delete this[n]);t.size>0&&(this._$Ep=t)}createRenderRoot(){let t=this.shadowRoot??this.attachShadow(this.constructor.shadowRootOptions);return Pt(t,this.constructor.elementStyles),t}connectedCallback(){this.renderRoot??=this.createRenderRoot(),this.enableUpdating(!0),this._$EO?.forEach(t=>t.hostConnected?.())}enableUpdating(t){}disconnectedCallback(){this._$EO?.forEach(t=>t.hostDisconnected?.())}attributeChangedCallback(t,e,n){this._$AK(t,n)}_$ET(t,e){let n=this.constructor.elementProperties.get(t),o=this.constructor._$Eu(t,n);if(o!==void 0&&n.reflect===!0){let s=(n.converter?.toAttribute!==void 0?n.converter:ct).toAttribute(e,n.type);this._$Em=t,s==null?this.removeAttribute(o):this.setAttribute(o,s),this._$Em=null}}_$AK(t,e){let n=this.constructor,o=n._$Eh.get(t);if(o!==void 0&&this._$Em!==o){let s=n.getPropertyOptions(o),r=typeof s.converter=="function"?{fromAttribute:s.converter}:s.converter?.fromAttribute!==void 0?s.converter:ct;this._$Em=o;let l=r.fromAttribute(e,s.type);this[o]=l??this._$Ej?.get(o)??l,this._$Em=null}}requestUpdate(t,e,n,o=!1,s){if(t!==void 0){let r=this.constructor;if(o===!1&&(s=this[t]),n??=r.getPropertyOptions(t),!((n.hasChanged??Mt)(s,e)||n.useDefault&&n.reflect&&s===this._$Ej?.get(t)&&!this.hasAttribute(r._$Eu(t,n))))return;this.C(t,e,n)}this.isUpdatePending===!1&&(this._$ES=this._$EP())}C(t,e,{useDefault:n,reflect:o,wrapped:s},r){n&&!(this._$Ej??=new Map).has(t)&&(this._$Ej.set(t,r??e??this[t]),s!==!0||r!==void 0)||(this._$AL.has(t)||(this.hasUpdated||n||(e=void 0),this._$AL.set(t,e)),o===!0&&this._$Em!==t&&(this._$Eq??=new Set).add(t))}async _$EP(){this.isUpdatePending=!0;try{await this._$ES}catch(e){Promise.reject(e)}let t=this.scheduleUpdate();return t!=null&&await t,!this.isUpdatePending}scheduleUpdate(){return this.performUpdate()}performUpdate(){if(!this.isUpdatePending)return;if(!this.hasUpdated){if(this.renderRoot??=this.createRenderRoot(),this._$Ep){for(let[o,s]of this._$Ep)this[o]=s;this._$Ep=void 0}let n=this.constructor.elementProperties;if(n.size>0)for(let[o,s]of n){let{wrapped:r}=s,l=this[o];r!==!0||this._$AL.has(o)||l===void 0||this.C(o,void 0,s,l)}}let t=!1,e=this._$AL;try{t=this.shouldUpdate(e),t?(this.willUpdate(e),this._$EO?.forEach(n=>n.hostUpdate?.()),this.update(e)):this._$EM()}catch(n){throw t=!1,this._$EM(),n}t&&this._$AE(e)}willUpdate(t){}_$AE(t){this._$EO?.forEach(e=>e.hostUpdated?.()),this.hasUpdated||(this.hasUpdated=!0,this.firstUpdated(t)),this.updated(t)}_$EM(){this._$AL=new Map,this.isUpdatePending=!1}get updateComplete(){return this.getUpdateComplete()}getUpdateComplete(){return this._$ES}shouldUpdate(t){return!0}update(t){this._$Eq&&=this._$Eq.forEach(e=>this._$ET(e,this[e])),this._$EM()}updated(t){}firstUpdated(t){}};$.elementStyles=[],$.shadowRootOptions={mode:"open"},$[N("elementProperties")]=new Map,$[N("finalized")]=new Map,Ue?.({ReactiveElement:$}),(Z.reactiveElementVersions??=[]).push("2.1.2");var yt=globalThis,Ot=i=>i,J=yt.trustedTypes,Nt=J?J.createPolicy("lit-html",{createHTML:i=>i}):void 0,jt="$lit$",w=`lit$${Math.random().toFixed(9).slice(2)}$`,Vt="?"+w,Le=`<${Vt}>`,C=document,L=()=>C.createComment(""),D=i=>i===null||typeof i!="object"&&typeof i!="function",_t=Array.isArray,De=i=>_t(i)||typeof i?.[Symbol.iterator]=="function",ut=`[ 	
\f\r]`,U=/<(?:(!--|\/[^a-zA-Z])|(\/?[a-zA-Z][^>\s]*)|(\/?$))/g,Ut=/-->/g,Lt=/>/g,k=RegExp(`>|${ut}(?:([^\\s"'>=/]+)(${ut}*=${ut}*(?:[^ 	
\f\r"'\`<>=]|("|')|))|$)`,"g"),Dt=/'/g,It=/"/g,Bt=/^(?:script|style|textarea|title)$/i,bt=i=>(t,...e)=>({_$litType$:i,strings:t,values:e}),p=bt(1),fn=bt(2),gn=bt(3),x=Symbol.for("lit-noChange"),u=Symbol.for("lit-nothing"),zt=new WeakMap,S=C.createTreeWalker(C,129);function Ft(i,t){if(!_t(i)||!i.hasOwnProperty("raw"))throw Error("invalid template strings array");return Nt!==void 0?Nt.createHTML(t):t}var Ie=(i,t)=>{let e=i.length-1,n=[],o,s=t===2?"<svg>":t===3?"<math>":"",r=U;for(let l=0;l<e;l++){let a=i[l],h,m,c=-1,f=0;for(;f<a.length&&(r.lastIndex=f,m=r.exec(a),m!==null);)f=r.lastIndex,r===U?m[1]==="!--"?r=Ut:m[1]!==void 0?r=Lt:m[2]!==void 0?(Bt.test(m[2])&&(o=RegExp("</"+m[2],"g")),r=k):m[3]!==void 0&&(r=k):r===k?m[0]===">"?(r=o??U,c=-1):m[1]===void 0?c=-2:(c=r.lastIndex-m[2].length,h=m[1],r=m[3]===void 0?k:m[3]==='"'?It:Dt):r===It||r===Dt?r=k:r===Ut||r===Lt?r=U:(r=k,o=void 0);let g=r===k&&i[l+1].startsWith("/>")?" ":"";s+=r===U?a+Le:c>=0?(n.push(h),a.slice(0,c)+jt+a.slice(c)+w+g):a+w+(c===-2?l:g)}return[Ft(i,s+(i[e]||"<?>")+(t===2?"</svg>":t===3?"</math>":"")),n]},I=class i{constructor({strings:t,_$litType$:e},n){let o;this.parts=[];let s=0,r=0,l=t.length-1,a=this.parts,[h,m]=Ie(t,e);if(this.el=i.createElement(h,n),S.currentNode=this.el.content,e===2||e===3){let c=this.el.content.firstChild;c.replaceWith(...c.childNodes)}for(;(o=S.nextNode())!==null&&a.length<l;){if(o.nodeType===1){if(o.hasAttributes())for(let c of o.getAttributeNames())if(c.endsWith(jt)){let f=m[r++],g=o.getAttribute(c).split(w),E=/([.?@])?(.*)/.exec(f);a.push({type:1,index:s,name:E[2],strings:g,ctor:E[1]==="."?ht:E[1]==="?"?mt:E[1]==="@"?ft:P}),o.removeAttribute(c)}else c.startsWith(w)&&(a.push({type:6,index:s}),o.removeAttribute(c));if(Bt.test(o.tagName)){let c=o.textContent.split(w),f=c.length-1;if(f>0){o.textContent=J?J.emptyScript:"";for(let g=0;g<f;g++)o.append(c[g],L()),S.nextNode(),a.push({type:2,index:++s});o.append(c[f],L())}}}else if(o.nodeType===8)if(o.data===Vt)a.push({type:2,index:s});else{let c=-1;for(;(c=o.data.indexOf(w,c+1))!==-1;)a.push({type:7,index:s}),c+=w.length-1}s++}}static createElement(t,e){let n=C.createElement("template");return n.innerHTML=t,n}};function T(i,t,e=i,n){if(t===x)return t;let o=n!==void 0?e._$Co?.[n]:e._$Cl,s=D(t)?void 0:t._$litDirective$;return o?.constructor!==s&&(o?._$AO?.(!1),s===void 0?o=void 0:(o=new s(i),o._$AT(i,e,n)),n!==void 0?(e._$Co??=[])[n]=o:e._$Cl=o),o!==void 0&&(t=T(i,o._$AS(i,t.values),o,n)),t}var pt=class{constructor(t,e){this._$AV=[],this._$AN=void 0,this._$AD=t,this._$AM=e}get parentNode(){return this._$AM.parentNode}get _$AU(){return this._$AM._$AU}u(t){let{el:{content:e},parts:n}=this._$AD,o=(t?.creationScope??C).importNode(e,!0);S.currentNode=o;let s=S.nextNode(),r=0,l=0,a=n[0];for(;a!==void 0;){if(r===a.index){let h;a.type===2?h=new z(s,s.nextSibling,this,t):a.type===1?h=new a.ctor(s,a.name,a.strings,this,t):a.type===6&&(h=new gt(s,this,t)),this._$AV.push(h),a=n[++l]}r!==a?.index&&(s=S.nextNode(),r++)}return S.currentNode=C,o}p(t){let e=0;for(let n of this._$AV)n!==void 0&&(n.strings!==void 0?(n._$AI(t,n,e),e+=n.strings.length-2):n._$AI(t[e])),e++}},z=class i{get _$AU(){return this._$AM?._$AU??this._$Cv}constructor(t,e,n,o){this.type=2,this._$AH=u,this._$AN=void 0,this._$AA=t,this._$AB=e,this._$AM=n,this.options=o,this._$Cv=o?.isConnected??!0}get parentNode(){let t=this._$AA.parentNode,e=this._$AM;return e!==void 0&&t?.nodeType===11&&(t=e.parentNode),t}get startNode(){return this._$AA}get endNode(){return this._$AB}_$AI(t,e=this){t=T(this,t,e),D(t)?t===u||t==null||t===""?(this._$AH!==u&&this._$AR(),this._$AH=u):t!==this._$AH&&t!==x&&this._(t):t._$litType$!==void 0?this.$(t):t.nodeType!==void 0?this.T(t):De(t)?this.k(t):this._(t)}O(t){return this._$AA.parentNode.insertBefore(t,this._$AB)}T(t){this._$AH!==t&&(this._$AR(),this._$AH=this.O(t))}_(t){this._$AH!==u&&D(this._$AH)?this._$AA.nextSibling.data=t:this.T(C.createTextNode(t)),this._$AH=t}$(t){let{values:e,_$litType$:n}=t,o=typeof n=="number"?this._$AC(t):(n.el===void 0&&(n.el=I.createElement(Ft(n.h,n.h[0]),this.options)),n);if(this._$AH?._$AD===o)this._$AH.p(e);else{let s=new pt(o,this),r=s.u(this.options);s.p(e),this.T(r),this._$AH=s}}_$AC(t){let e=zt.get(t.strings);return e===void 0&&zt.set(t.strings,e=new I(t)),e}k(t){_t(this._$AH)||(this._$AH=[],this._$AR());let e=this._$AH,n,o=0;for(let s of t)o===e.length?e.push(n=new i(this.O(L()),this.O(L()),this,this.options)):n=e[o],n._$AI(s),o++;o<e.length&&(this._$AR(n&&n._$AB.nextSibling,o),e.length=o)}_$AR(t=this._$AA.nextSibling,e){for(this._$AP?.(!1,!0,e);t!==this._$AB;){let n=Ot(t).nextSibling;Ot(t).remove(),t=n}}setConnected(t){this._$AM===void 0&&(this._$Cv=t,this._$AP?.(t))}},P=class{get tagName(){return this.element.tagName}get _$AU(){return this._$AM._$AU}constructor(t,e,n,o,s){this.type=1,this._$AH=u,this._$AN=void 0,this.element=t,this.name=e,this._$AM=o,this.options=s,n.length>2||n[0]!==""||n[1]!==""?(this._$AH=Array(n.length-1).fill(new String),this.strings=n):this._$AH=u}_$AI(t,e=this,n,o){let s=this.strings,r=!1;if(s===void 0)t=T(this,t,e,0),r=!D(t)||t!==this._$AH&&t!==x,r&&(this._$AH=t);else{let l=t,a,h;for(t=s[0],a=0;a<s.length-1;a++)h=T(this,l[n+a],e,a),h===x&&(h=this._$AH[a]),r||=!D(h)||h!==this._$AH[a],h===u?t=u:t!==u&&(t+=(h??"")+s[a+1]),this._$AH[a]=h}r&&!o&&this.j(t)}j(t){t===u?this.element.removeAttribute(this.name):this.element.setAttribute(this.name,t??"")}},ht=class extends P{constructor(){super(...arguments),this.type=3}j(t){this.element[this.name]=t===u?void 0:t}},mt=class extends P{constructor(){super(...arguments),this.type=4}j(t){this.element.toggleAttribute(this.name,!!t&&t!==u)}},ft=class extends P{constructor(t,e,n,o,s){super(t,e,n,o,s),this.type=5}_$AI(t,e=this){if((t=T(this,t,e,0)??u)===x)return;let n=this._$AH,o=t===u&&n!==u||t.capture!==n.capture||t.once!==n.once||t.passive!==n.passive,s=t!==u&&(n===u||o);o&&this.element.removeEventListener(this.name,this,n),s&&this.element.addEventListener(this.name,this,t),this._$AH=t}handleEvent(t){typeof this._$AH=="function"?this._$AH.call(this.options?.host??this.element,t):this._$AH.handleEvent(t)}},gt=class{constructor(t,e,n){this.element=t,this.type=6,this._$AN=void 0,this._$AM=e,this.options=n}get _$AU(){return this._$AM._$AU}_$AI(t){T(this,t)}};var ze=yt.litHtmlPolyfillSupport;ze?.(I,z),(yt.litHtmlVersions??=[]).push("3.3.3");var Kt=(i,t,e)=>{let n=e?.renderBefore??t,o=n._$litPart$;if(o===void 0){let s=e?.renderBefore??null;n._$litPart$=o=new z(t.insertBefore(L(),s),s,void 0,e??{})}return o._$AI(i),o};var vt=globalThis,b=class extends ${constructor(){super(...arguments),this.renderOptions={host:this},this._$Do=void 0}createRenderRoot(){let t=super.createRenderRoot();return this.renderOptions.renderBefore??=t.firstChild,t}update(t){let e=this.render();this.hasUpdated||(this.renderOptions.isConnected=this.isConnected),super.update(t),this._$Do=Kt(e,this.renderRoot,this.renderOptions)}connectedCallback(){super.connectedCallback(),this._$Do?.setConnected(!0)}disconnectedCallback(){super.disconnectedCallback(),this._$Do?.setConnected(!1)}render(){return x}};b._$litElement$=!0,b.finalized=!0,vt.litElementHydrateSupport?.({LitElement:b});var je=vt.litElementPolyfillSupport;je?.({LitElement:b});(vt.litElementVersions??=[]).push("4.2.2");async function j(i,t,e,n,o){try{await i.callService(t,e,n,{entity_id:o})}catch{}}function V(i,t,e){return j(i,"number","set_value",{value:e},t)}function B(i,t,e){return j(i,"timerify","add_time",{minutes:e},t)}function qt(i,t){return j(i,"timerify","run",{},t)}function Wt(i,t,e){return j(i,"switch",e?"turn_on":"turn_off",{},t)}function Gt(i,t,e){return j(i,"timerify","cancel_command",{command_id:e},t)}var Yt={card_entity_not_found:"Entity not found: {entity}",card_not_a_timer:"{entity} is not the Run for number of a Timerify timer",card_timer_incomplete:"The timer of {entity} cannot be shown: its target or one of its sensors is missing. Open the timer's page to see why.",card_not_allowed:"You are not allowed to see the timer {entity}",card_ends_at_disabled:"The Ends at sensor of this timer, {sensor}, is disabled. Enable it for the card to work",card_error_entity:"Choose the Run for number of a timer",card_error_layout:"The layout is pill or round",card_error_presets:"Presets are whole minutes from 1 to 1440",card_error_chip:"The quick chip is whole minutes from 1 to 1440",card_close:"Close",card_until:"until {time}",card_add_time:"Add {duration}",card_subtract_time:"Take off {duration}",card_stop:"Stop",card_schedule:"Schedule",card_commands:"Pending commands",card_commands_disabled:"Pending commands are hidden: the Next command sensor, {sensor}, is disabled",card_command_on:"On at {time}",card_command_on_for:"On at {time} for {duration}",card_command_off:"Off at {time}",card_cancel_command:"Cancel",card_settings:"Settings",card_picker_description:"The countdown, presets and schedule of a Timerify timer",card_editor_entity:"Timer",card_editor_layout:"Layout",card_editor_layout_pill:"Pill",card_editor_layout_round:"Round",card_editor_name:"Name",card_editor_icon:"Icon",card_editor_presets:"Duration presets (minutes)",card_editor_presets_helper:"Leave empty for {presets}",card_editor_chip:"Quick add chip (minutes, pill only)"};var Zt="common",Jt="timerify",Ve=`component.${Jt}.${Zt}.`;function $t(i){return Ve+i}function Be(i,t){return i.replace(/\{(\w+)\}/g,(e,n)=>String(t?.[n]??e))}function d(i,t,e){return i?.localize($t(t),e)||Be(Yt[t],e)}var F,Xt=Promise.resolve(),Qt,te=new Set;function Q(i){return i.language!==F&&(F=i.language,Xt=Fe(i,i.language)),Xt}async function Fe(i,t){let e;try{e=await i.loadBackendTranslation(Zt,Jt)}catch{F===t&&(F=void 0);return}F===t&&(Qt={...i,localize:e},te.forEach(n=>n()))}function A(){return Qt}function ee(i){te.add(i)}var K=[15,30,45,60,120],xt=1440,_=class extends Error{constructor(e){super(d(A(),e));this.key=e}key};function ie(i){let t=typeof i=="number"?i:typeof i=="string"&&/^\d+$/.test(i)?Number(i):void 0;return t!==void 0&&Number.isInteger(t)&&t>=1&&t<=xt?t:void 0}function Ke(i){if(i===void 0||Array.isArray(i)&&i.length===0)return[...K];if(!Array.isArray(i))throw new _("card_error_presets");let t=new Set;for(let e of i){let n=ie(e);if(n===void 0)throw new _("card_error_presets");t.add(n)}return[...t]}function qe(i){if(i===void 0)return;let t=ie(i);if(t===void 0)throw new _("card_error_chip");return t}var oe=i=>typeof i=="object"&&i!==null?i:{},ne=i=>typeof i=="number"||typeof i=="string";function se(i){let{entity:t,layout:e,presets:n,chip:o}=oe(i);if(t!==void 0&&typeof t!="string")throw new _("card_error_entity");if(e!==void 0&&typeof e!="string")throw new _("card_error_layout");if(n!==void 0&&!(Array.isArray(n)&&n.every(ne)))throw new _("card_error_presets");if(o!==void 0&&!ne(o))throw new _("card_error_chip")}function re(i){let t=oe(i),{entity:e,layout:n="pill",name:o,icon:s}=t;if(typeof e!="string"||!/^number\.[a-z0-9_]+$/.test(e))throw new _("card_error_entity");if(n!=="pill"&&n!=="round")throw new _("card_error_layout");let r=qe(t.chip);return{entity:e,layout:n,...typeof o=="string"&&o!==""&&{name:o},...typeof s=="string"&&s!==""&&{icon:s},presets:Ke(t.presets),...r!==void 0&&{chip:r}}}var tt=class{#t;#i;#e;#n=!1;#o;constructor(t,e,n){this.#t=t,this.#i=e,this.#e=n,t.addController(this)}hostConnected(){this.#n=!0,this.#s()}hostUpdated(){this.#s()}hostDisconnected(){this.#n=!1,this.#s()}#s(){let t=this.#i(),e=this.#n&&t!==void 0&&t.getTime()>this.#e();e&&this.#o===void 0?this.#o=setInterval(()=>this.#t.requestUpdate(),1e3):!e&&this.#o!==void 0&&(clearInterval(this.#o),this.#o=void 0)}};var ae=i=>String(i).padStart(2,"0");function H(i){let t=Math.ceil(Math.max(0,i)),e=Math.floor(t/3600),n=Math.floor(t%3600/60),o=ae(t%60);return e>0?`${e}:${ae(n)}:${o}`:`${n}:${o}`}function We({language:i,time_format:t}){if(t==="12"||t==="24")return t==="12";let e=new Intl.DateTimeFormat(t==="language"?i:void 0,{hour:"numeric"}).resolvedOptions();return e.hourCycle==="h11"||e.hourCycle==="h12"}var Ge=864e5;function le(i,t){let e=new Intl.DateTimeFormat("en-US",{timeZone:i,year:"numeric",month:"numeric",day:"numeric"}).formatToParts(t),n=o=>Number(e.find(s=>s.type===o)?.value);return Date.UTC(n("year"),n("month")-1,n("day"))/Ge}function q(i,t,e){let{locale:n}=i,o=n.time_zone==="server"?i.config.time_zone:void 0,s=le(o,t.getTime())-le(o,e),r=s===0?{}:s>=1&&s<=6?{weekday:"short"}:{month:"short",day:"numeric"};return new Intl.DateTimeFormat(n.language,{...r,hour:"numeric",minute:"2-digit",hourCycle:We(n)?"h12":"h23",timeZone:o}).format(t)}function v(i,t){let e=(r,l)=>new Intl.NumberFormat(i.locale.language,{style:"unit",unit:l,unitDisplay:"short",useGrouping:!1}).format(r),n=Math.floor(t/60),o=t%60,s=n>0?[e(n,"hour")]:[];return(o>0||n===0)&&s.push(e(o,"minute")),s.join(" ")}function de(i,t,e,n,o){return e.includes(n)&&typeof o=="number"?new Intl.NumberFormat(i.locale.language,{style:"percent",maximumFractionDigits:1}).format(o/100):t===void 0?String(o):n==="hvac_mode"?i.formatEntityState(t,String(o)):i.formatEntityAttributeValue(t,n,o)}var ce={entity:"card_editor_entity",layout:"card_editor_layout",name:"card_editor_name",icon:"card_editor_icon",presets:"card_editor_presets",chip:"card_editor_chip"},Ye=i=>Object.hasOwn(ce,i),Xe={locale:{language:"en"}};function ue(){return A()??Xe}function Ze(){let i=ue();return new Intl.ListFormat(i.locale.language,{style:"long",type:"conjunction"}).format(K.map(t=>v(i,t)))}async function pe(){let i=A();return{schema:[{name:"entity",required:!0,selector:{entity:{filter:{integration:"timerify",domain:"number"}}}},{name:"layout",selector:{select:{options:[{value:"pill",label:d(i,"card_editor_layout_pill")},{value:"round",label:d(i,"card_editor_layout_round")}]}}},{name:"",type:"grid",schema:[{name:"name",selector:{text:{}}},{name:"icon",selector:{icon:{}}}]},{name:"presets",selector:{select:{multiple:!0,custom_value:!0,options:K.map(t=>({value:String(t),label:v(ue(),t)}))}}},{name:"chip",selector:{number:{min:1,max:xt,mode:"box"}}}],assertConfig:se,computeLabel:({name:t},e)=>Ye(t)?e($t(ce[t])):"",computeHelper:({name:t})=>t==="presets"?d(A(),"card_editor_presets_helper",{presets:Ze()}):void 0}}function he(i,t,e){Q(i);let n=s=>{let r=i.entities[s];return r?.platform==="timerify"&&r.translation_key==="run_for"},o=s=>s.filter(n).sort()[0];return{entity:o(t)??o(e)??o(Object.keys(i.entities))??"",layout:"pill",presets:K.map(String)}}var Je="not_found",Qe="timer_incomplete",tn="unauthorized";async function fe(i,t){let e=Date.now();try{let n=await i.callWS({type:"timerify/timer",entity_id:t}),o=wt(n.server_time),s=o===void 0?0:o-(e+Date.now())/2;return{status:"found",info:n,clockOffset:s}}catch(n){let o=typeof n=="object"&&n!==null&&"code"in n?n.code:"";return o===Je?{status:"not_found"}:o===Qe?{status:"incomplete"}:{status:o===tn?"unauthorized":"failed"}}}var W=i=>Date.now()+(i.status==="found"?i.clockOffset:0),et=(i,t)=>i.disabled_sensors.includes(t),R=i=>i!==void 0&&i.state!=="unavailable"&&i.state!=="unknown";function en(i,t){return i===void 0||i.state==="unavailable"||i.state==="unknown"?!1:t.states.includes(i.state)===(t.match==="is")}var nn="mdi:timer-outline",me=i=>i===void 0||i.state==="unavailable";function wt(i){let t=typeof i=="string"?Date.parse(i):Number.NaN;return Number.isNaN(t)?void 0:t}function ge(i,t,e,n){let o=e.status==="found"?e.info:void 0,s=i.states[t.entity],r=o&&i.states[o.target],l=t.name||r&&i.formatEntityName(r,void 0)||s?.attributes.friendly_name||t.entity,a=t.icon?{icon:t.icon}:r?{stateObj:r}:{icon:nn},h={name:l,icon:a,target:r,remaining:0},m=o&&i.states[o.ends_at];if(o===void 0||m===void 0||me(s)||me(m))return{...h,state:"unavailable",progress:0};let c=wt(m.state);if(c===void 0)return en(r,o.target_on)?{...h,state:"open",progress:1}:{...h,state:"idle",progress:0};let f=wt(m.attributes.started_at),g=f===void 0?0:(c-f)/1e3,E=Math.max(0,(c-n)/1e3);return{...h,state:"counting",remaining:E,progress:g>0?Math.min(1,E/g):1,endsAt:new Date(c)}}function nt(i,t){return t?[i,t.ends_at,t.next_command,t.target,...t.intervals.map(({entity_id:e})=>e)]:[i]}var on=["locale","language","localize","config","user","connected","entities","formatEntityName","formatEntityState","formatEntityAttributeValue"];function it(i,t,e){for(let o of i.keys())if(o!=="hass")return!0;let n=i.get("hass");return n===void 0||t===void 0?!0:on.some(o=>n[o]!==t[o])||e.some(o=>n.states[o]!==t.states[o])}function ot(i){return"stateObj"in i.icon?p`<ha-state-icon .stateObj=${i.icon.stateObj}></ha-state-icon>`:p`<ha-icon .icon=${i.icon.icon}></ha-icon>`}function sn(i,t,e){if(i.state!=="unavailable")return i.target?e.formatEntityState(i.target):"";let n=e.states[t.entity];if(R(n))return"";let o={entity_id:t.entity,state:"unavailable",attributes:{}};return e.formatEntityState(n??o,"unavailable")}function st(i,t,e,n){if(i.state!=="counting"||i.endsAt===void 0)return sn(i,t,e);let o=q(e,i.endsAt,n);return p`
    <span class="remaining">${H(i.remaining)}</span>
    <span class="until">${d(e,"card_until",{time:o})}</span>
  `}var ye=y`
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
`;var _e={ATTRIBUTE:1,CHILD:2,PROPERTY:3,BOOLEAN_ATTRIBUTE:4,EVENT:5,ELEMENT:6},be=i=>(...t)=>({_$litDirective$:i,values:t}),rt=class{constructor(t){}get _$AU(){return this._$AM._$AU}_$AT(t,e,n){this._$Ct=t,this._$AM=e,this._$Ci=n}_$AS(t,e){return this.update(t,e)}update(t,e){return this.render(...e)}};var ve="important",rn=" !"+ve,$e=be(class extends rt{constructor(i){if(super(i),i.type!==_e.ATTRIBUTE||i.name!=="style"||i.strings?.length>2)throw Error("The `styleMap` directive must be used in the `style` attribute and must be the only part in the attribute.")}render(i){return Object.keys(i).reduce((t,e)=>{let n=i[e];return n==null?t:t+`${e=e.includes("-")?e:e.replace(/(?:^(webkit|moz|ms|o)|)(?=[A-Z])/g,"-$&").toLowerCase()}:${n};`},"")}update(i,[t]){let{style:e}=i.element;if(this.ft===void 0)return this.ft=new Set(Object.keys(t)),this.render(t);for(let n of this.ft)t[n]==null&&(this.ft.delete(n),n.includes("-")?e.removeProperty(n):e[n]=null);for(let n in t){let o=t[n];if(o!=null){this.ft.add(n);let s=typeof o=="string"&&o.endsWith(rn);n.includes("-")||s?e.setProperty(n,s?o.slice(0,-11):o,s?ve:""):e[n]=o}}return x}});function xe(i,t,e,n,o,s){let r=Math.round(i.progress*1e3)/10;return p`
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
          <span class="fill" style=${$e({width:`${r}%`})}></span>
        </span>
      </div>
      <div class="content">
        <span class="icon">${ot(i)}</span>
        <span class="text" id="label">
          <span class="name">${i.name}</span>
          <span class="status">${st(i,t,e,s)}</span>
        </span>
        ${t.chip===void 0?u:p`
              <button
                class="chip"
                type="button"
                aria-label=${d(e,"card_add_time",{duration:v(e,t.chip)})}
                ?disabled=${i.state==="unavailable"}
                @click=${o}
              >
                +${v(e,t.chip)}
              </button>
            `}
      </div>
    </ha-card>
  `}var we=y`
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
`;function an(i){let t=i?.attributes.commands;return Array.isArray(t)?t.flatMap(e=>{if(typeof e!="object"||e===null)return[];let{id:n,at:o,action:s,minutes:r,settings:l}=e,a=typeof o=="string"?new Date(o):void 0;return typeof n!="string"||a===void 0||Number.isNaN(a.getTime())||s!=="on"&&s!=="off"?[]:[{id:n,at:a,action:s,minutes:typeof r=="number"&&r>0?r:null,settings:typeof l=="object"&&l!==null?Object.entries(l):[]}]}):[]}var ln=i=>`/config/integrations/integration/timerify#config_entry=${encodeURIComponent(i)}`,at=class extends b{static properties={hass:{attribute:!1},config:{attribute:!1},lookup:{attribute:!1},view:{attribute:!1},opened:{state:!0}};static styles=y`
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
  `;constructor(){super(),this.opened=!1}open(){this.opened=!0}close(){this.#t?.close(),this.#a()}disconnectedCallback(){super.disconnectedCallback(),this.close()}get#t(){return this.renderRoot.querySelector("dialog")}#i=()=>{this.#t?.open||this.#a()};#e=!1;#n=t=>{this.#e=t.target===t.currentTarget};#o=t=>{this.#e&&=t.target===t.currentTarget};#s=()=>{this.#e=!1};#r=t=>{let e=this.#e&&t.target===t.currentTarget;this.#e=!1,e&&this.close()};#a(){this.opened&&(this.opened=!1,this.dispatchEvent(new CustomEvent("closed")))}shouldUpdate(t){if(!this.hasUpdated||t.has("opened"))return!0;let e=nt(this.config.entity,this.lookup.info);return this.opened&&it(t,this.hass,e)}updated(t){let e=this.#t;t.has("opened")&&this.opened&&e&&!e.open&&e.showModal()}render(){return p`
      <dialog
        aria-labelledby="title"
        @cancel=${()=>this.close()}
        @close=${this.#i}
        @pointerdown=${this.#n}
        @pointerup=${this.#o}
        @pointercancel=${this.#s}
        @click=${this.#r}
      >
        ${this.opened?this.#d():u}
      </dialog>
    `}#d(){let{hass:t,view:e}=this,n=W(this.lookup);return p`
      <div class="wrapper">
        <header>
          <h2 id="title">${e.name}</h2>
          <button class="close" @click=${()=>this.close()}>${d(t,"card_close")}</button>
        </header>
        ${this.#l(n)} ${this.#c()} ${this.#p()} ${this.#h(n)}
        ${this.#f()}
      </div>
    `}#l(t){let{hass:e,view:n}=this;if(n.state!=="counting"||n.endsAt===void 0)return u;let o=q(e,n.endsAt,t);return p`
      <p class="countdown">
        <span class="remaining">${H(n.remaining)}</span>
        <span class="until">${d(e,"card_until",{time:o})}</span>
      </p>
    `}#c(){let{hass:t,config:e,view:n}=this,o=v(t,5),s=n.state==="counting",r=s||n.state==="open",l=n.state==="unavailable";return p`
      <div class="presets">
        ${e.presets.map(a=>p`
            <button
              class="action preset"
              ?disabled=${l}
              @click=${()=>{V(t,e.entity,a)}}
            >
              ${v(t,a)}
            </button>
          `)}
      </div>
      <div class="adjust">
        <button
          class="action step"
          aria-label=${d(t,"card_subtract_time",{duration:o})}
          ?disabled=${!s}
          @click=${()=>{B(t,e.entity,-5)}}
        >
          −${o}
        </button>
        <button
          class="action step"
          aria-label=${d(t,"card_add_time",{duration:o})}
          ?disabled=${l}
          @click=${()=>{B(t,e.entity,5)}}
        >
          +${o}
        </button>
        <button
          class="action stop"
          ?disabled=${!r}
          @click=${()=>{V(t,e.entity,0)}}
        >
          ${d(t,"card_stop")}
        </button>
      </div>
    `}#p(){let{intervals:t}=this.lookup.info;return t.length===0?u:p`
      <section class="schedule">
        <h3>${d(this.hass,"card_schedule")}</h3>
        <ul>
          ${t.map(e=>p`<li>${this.#u(e)}</li>`)}
        </ul>
      </section>
    `}#u({entity_id:t,title:e}){let{hass:n}=this,o=n.states[t],s=o!==void 0&&o.state!=="unavailable",r=s&&o.state==="on",l=o??{entity_id:t,state:"unavailable",attributes:{}};return p`
      <button
        class="interval"
        role="switch"
        aria-checked=${r?"true":"false"}
        ?disabled=${!s}
        @click=${()=>{Wt(n,t,!r)}}
      >
        <span class="label">
          <span class="title">${e}</span>
          ${s?u:p`<span class="state">${n.formatEntityState(l,"unavailable")}</span>`}
        </span>
        <span class="track" aria-hidden="true"><span class="knob"></span></span>
      </button>
    `}#h(t){let{hass:e,config:n,view:o}=this,{info:s}=this.lookup;if(et(s,s.next_command))return p`
        <section class="commands">
          <p class="note">${d(e,"card_commands_disabled",{sensor:s.next_command})}</p>
        </section>
      `;let r=an(e.states[s.next_command]);if(r.length===0)return u;let l=o.state==="unavailable";return p`
      <section class="commands">
        <h3>${d(e,"card_commands")}</h3>
        <ul>
          ${r.map((a,h)=>{let m=a.settings.map(([c,f])=>de(e,o.target,s.percent_settings,c,f));return p`
              <li>
                <div class="command" id="command-${h}">
                  <span class="what">${this.#m(a,t)}</span>
                  ${m.length===0?u:p`<span class="settings">${m.join(", ")}</span>`}
                </div>
                <button
                  class="cancel"
                  aria-label=${d(e,"card_cancel_command")}
                  aria-describedby="command-${h}"
                  ?disabled=${l}
                  @click=${()=>{Gt(e,n.entity,a.id)}}
                >
                  <span aria-hidden="true">×</span>
                </button>
              </li>
            `})}
        </ul>
      </section>
    `}#m(t,e){let{hass:n}=this,o=q(n,t.at,e);return t.action==="off"?d(n,"card_command_off",{time:o}):t.minutes===null?d(n,"card_command_on",{time:o}):d(n,"card_command_on_for",{time:o,duration:v(n,t.minutes)})}#f(){return this.hass.user?.is_admin?p`
      <footer>
        <a href=${ln(this.lookup.info.entry_id)} @click=${this.#g}>
          ${d(this.hass,"card_settings")}
        </a>
      </footer>
    `:u}#g=t=>{!t.ctrlKey&&!t.metaKey&&!t.shiftKey&&this.close()}};var Ae="data-held",G=class{#t;#i;#e=!1;#n;#o;#s=!1;#r=!1;constructor(t,e){this.#t=t,this.#i=e,t.addController(this)}hostDisconnected(){this.#e=!1,this.#r=!1,this.#l()}binding(){let t={click:n=>{if(this.#r){this.#r=!1,n.preventDefault(),n.stopPropagation();return}this.#i.tap()},keydown:n=>{n.key==="Enter"?(n.preventDefault(),n.repeat||this.#i.tap()):n.key===" "&&(n.preventDefault(),this.#e=!0)},keyup:n=>{if(n.key!==" ")return;let o=this.#e;this.#e=!1,o&&this.#i.tap()}},{hold:e}=this.#i;return e===void 0?t:{...t,pointerdown:n=>this.#a(n),pointerup:n=>{if(n.pointerId!==this.#n)return;let o=this.#s;this.#l(),o&&(this.#r=!0,e())},pointercancel:n=>this.#d(n),pointerleave:n=>this.#d(n),contextmenu:n=>{this.#n!==void 0&&n.preventDefault()}}}#a(t){!t.isPrimary||t.button!==0||(this.#r=!1,this.#l(),this.#n=t.pointerId,this.#o=setTimeout(()=>{this.#o=void 0,this.#s=!0,this.#t.setAttribute(Ae,"")},500))}#d(t){t.pointerId===this.#n&&this.#l()}#l(){clearTimeout(this.#o),this.#o=void 0,this.#n=void 0,this.#s=!1,this.#t.removeAttribute(Ae)}};var M=80,ke=6,Et=(M-ke)/2,Ee=2*Math.PI*Et;function dn(i){if(i.state!=="counting")return p`<span class="icon">${ot(i)}</span>`;let t=H(i.remaining);return p`<span class="time" aria-hidden="true">${t}</span>`}function Se(i,t,e,n,o){let s=M/2;return p`
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
            <circle class="track" cx=${s} cy=${s} r=${Et}></circle>
            <circle
              class="progress"
              cx=${s}
              cy=${s}
              r=${Et}
              transform="rotate(-90 ${s} ${s})"
              stroke-dasharray=${Ee}
              stroke-dashoffset=${(1-i.progress)*Ee}
            ></circle>
          </svg>
          <span class="centre">
            ${dn(i)}
          </span>
        </div>
        <span class="text" id="label">
          <span class="name">${i.name}</span>
          <span class="status">${st(i,t,e,o)}</span>
        </span>
      </div>
    </ha-card>
  `}var Ce=y`
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
    stroke-width: ${ke};
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
`;var kt="timerify-card",cn={pill:{columns:6,rows:1,min_columns:3,min_rows:1,max_rows:1},round:{columns:3,rows:2,min_columns:2,min_rows:2,max_rows:3}},St=class extends b{static properties={hass:{attribute:!1,noAccessor:!0},_config:{state:!0},_lookup:{state:!0}};static styles=[ye,we,Ce,y`
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
    `];static getConfigForm=pe;static getStubConfig=he;#t;#i=new Set;#e=!1;#n=!1;#o=new G(this,{tap:()=>this.#u?.open()}).binding();#s=new G(this,{tap:()=>this.#u?.open(),hold:()=>this.#h()}).binding();#r=()=>{let{_config:t,hass:e}=this;t?.chip!==void 0&&e!==void 0&&B(e,t.entity,t.chip)};#a;constructor(){super(),this._lookup={status:"pending"},new tt(this,()=>this.#a?.endsAt,()=>W(this._lookup))}get hass(){return this.#t}set hass(t){let e=this.#t;this.#t=t,this.requestUpdate("hass",e),this.#d(e,t)}setConfig(t){let e=re(t),n=this._config?.entity!==e.entity;this._config=e,n&&(this._lookup={status:"pending"},this.#c())}getCardSize(){return this._config?.layout==="round"?3:1}getGridOptions(){return cn[this._config?.layout??"pill"]}async getUpdateComplete(){let t=await super.getUpdateComplete();for(;this.#i.size>0;)await Promise.allSettled([...this.#i]),t=await super.getUpdateComplete();return t}#d(t,e){let n=t!==void 0&&e.connected&&!t.connected;(t===void 0||t.language!==e.language||n)&&this.#l(Q(e));let o=this._config?.entity;o!==void 0&&(t===void 0||t.entities!==e.entities||n||R(e.states[o])&&!R(t.states[o]))&&this.#c()}#l(t){let e=t.finally(()=>this.#i.delete(e));this.#i.add(e)}#c(){if(this.#e){this.#n=!0;return}this.#e=!0,this.#l(this.#p())}async#p(){try{do{this.#n=!1;let t=this._config?.entity;if(this.#t===void 0||t===void 0)return;let e=await fe(this.#t,t);this.#n||(this._lookup=e)}while(this.#n)}finally{this.#e=!1}}shouldUpdate(t){let e=this._lookup.status==="found"?this._lookup.info:void 0,n=this._config?nt(this._config.entity,e):[];return it(t,this.#t,n)}get#u(){return this.renderRoot.querySelector("timerify-card-popup")}#h(){let{_config:t,hass:e}=this,n=this.#a?.state;t===void 0||e===void 0||(n==="counting"||n==="open"?V(e,t.entity,0):n==="idle"&&qt(e,t.entity))}#m(t,e){let n=this._lookup;if(n.status==="unauthorized")return d(t,"card_not_allowed",{entity:e.entity});if(n.status==="incomplete")return d(t,"card_timer_incomplete",{entity:e.entity});if(n.status==="found"&&et(n.info,n.info.ends_at))return d(t,"card_ends_at_disabled",{sensor:n.info.ends_at});if(n.status!=="not_found")return;let o=t.states[e.entity];return o===void 0?d(t,"card_entity_not_found",{entity:e.entity}):R(o)?d(t,"card_not_a_timer",{entity:e.entity}):void 0}render(){let t=this.#t,e=this._config;if(!t||!e)return u;let n=this.#m(t,e);if(n)return this.#a=void 0,p`
        <ha-card>
          <div class="warning" role="alert">
            <ha-icon icon="mdi:alert-outline"></ha-icon>
            <span>${n}</span>
          </div>
        </ha-card>
      `;let o=W(this._lookup),s=ge(t,e,this._lookup,o);return this.#a=s,p`
      ${e.layout==="round"?Se(s,e,t,this.#s,o):xe(s,e,t,this.#o,this.#r,o)}
      ${this._lookup.status==="found"?p`
            <timerify-card-popup
              .hass=${t}
              .config=${e}
              .lookup=${this._lookup}
              .view=${s}
              @closed=${()=>this.renderRoot.querySelector(".body")?.focus()}
            ></timerify-card-popup>
          `:u}
    `}};if(!customElements.get(kt)){customElements.define("timerify-card-popup",at),customElements.define(kt,St);let i={type:kt,name:"Timerify",description:d(void 0,"card_picker_description"),preview:!0,documentationURL:"https://github.com/klimofey/timerify#dashboard-card"};(window.customCards??=[]).push(i),ee(()=>{i.description=d(A(),"card_picker_description")})}export{St as TimerifyCard};
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
