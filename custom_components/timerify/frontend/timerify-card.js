var Y=globalThis,X=Y.ShadowRoot&&(Y.ShadyCSS===void 0||Y.ShadyCSS.nativeShadow)&&"adoptedStyleSheets"in Document.prototype&&"replace"in CSSStyleSheet.prototype,ut=Symbol(),Lt=new WeakMap,N=class{constructor(t,e,n){if(this._$cssResult$=!0,n!==ut)throw Error("CSSResult is not constructable. Use `unsafeCSS` or `css` instead.");this.cssText=t,this.t=e}get styleSheet(){let t=this.o,e=this.t;if(X&&t===void 0){let n=e!==void 0&&e.length===1;n&&(t=Lt.get(e)),t===void 0&&((this.o=t=new CSSStyleSheet).replaceSync(this.cssText),n&&Lt.set(e,t))}return t}toString(){return this.cssText}},Nt=o=>new N(typeof o=="string"?o:o+"",void 0,ut),y=(o,...t)=>{let e=o.length===1?o[0]:t.reduce((n,i,s)=>n+(r=>{if(r._$cssResult$===!0)return r.cssText;if(typeof r=="number")return r;throw Error("Value passed to 'css' function must be a 'css' function result: "+r+". Use 'unsafeCSS' to pass non-literal values, but take care to ensure page security.")})(i)+o[s+1],o[0]);return new N(e,o,ut)},Ut=(o,t)=>{if(X)o.adoptedStyleSheets=t.map(e=>e instanceof CSSStyleSheet?e:e.styleSheet);else for(let e of t){let n=document.createElement("style"),i=Y.litNonce;i!==void 0&&n.setAttribute("nonce",i),n.textContent=e.cssText,o.appendChild(n)}},pt=X?o=>o:o=>o instanceof CSSStyleSheet?(t=>{let e="";for(let n of t.cssRules)e+=n.cssText;return Nt(e)})(o):o;var{is:Ue,defineProperty:De,getOwnPropertyDescriptor:Ie,getOwnPropertyNames:ze,getOwnPropertySymbols:je,getPrototypeOf:Ve}=Object,Z=globalThis,Dt=Z.trustedTypes,Be=Dt?Dt.emptyScript:"",Fe=Z.reactiveElementPolyfillSupport,U=(o,t)=>o,ht={toAttribute(o,t){switch(t){case Boolean:o=o?Be:null;break;case Object:case Array:o=o==null?o:JSON.stringify(o)}return o},fromAttribute(o,t){let e=o;switch(t){case Boolean:e=o!==null;break;case Number:e=o===null?null:Number(o);break;case Object:case Array:try{e=JSON.parse(o)}catch{e=null}}return e}},zt=(o,t)=>!Ue(o,t),It={attribute:!0,type:String,converter:ht,reflect:!1,useDefault:!1,hasChanged:zt};Symbol.metadata??=Symbol("metadata"),Z.litPropertyMetadata??=new WeakMap;var x=class extends HTMLElement{static addInitializer(t){this._$Ei(),(this.l??=[]).push(t)}static get observedAttributes(){return this.finalize(),this._$Eh&&[...this._$Eh.keys()]}static createProperty(t,e=It){if(e.state&&(e.attribute=!1),this._$Ei(),this.prototype.hasOwnProperty(t)&&((e=Object.create(e)).wrapped=!0),this.elementProperties.set(t,e),!e.noAccessor){let n=Symbol(),i=this.getPropertyDescriptor(t,n,e);i!==void 0&&De(this.prototype,t,i)}}static getPropertyDescriptor(t,e,n){let{get:i,set:s}=Ie(this.prototype,t)??{get(){return this[e]},set(r){this[e]=r}};return{get:i,set(r){let d=i?.call(this);s?.call(this,r),this.requestUpdate(t,d,n)},configurable:!0,enumerable:!0}}static getPropertyOptions(t){return this.elementProperties.get(t)??It}static _$Ei(){if(this.hasOwnProperty(U("elementProperties")))return;let t=Ve(this);t.finalize(),t.l!==void 0&&(this.l=[...t.l]),this.elementProperties=new Map(t.elementProperties)}static finalize(){if(this.hasOwnProperty(U("finalized")))return;if(this.finalized=!0,this._$Ei(),this.hasOwnProperty(U("properties"))){let e=this.properties,n=[...ze(e),...je(e)];for(let i of n)this.createProperty(i,e[i])}let t=this[Symbol.metadata];if(t!==null){let e=litPropertyMetadata.get(t);if(e!==void 0)for(let[n,i]of e)this.elementProperties.set(n,i)}this._$Eh=new Map;for(let[e,n]of this.elementProperties){let i=this._$Eu(e,n);i!==void 0&&this._$Eh.set(i,e)}this.elementStyles=this.finalizeStyles(this.styles)}static finalizeStyles(t){let e=[];if(Array.isArray(t)){let n=new Set(t.flat(1/0).reverse());for(let i of n)e.unshift(pt(i))}else t!==void 0&&e.push(pt(t));return e}static _$Eu(t,e){let n=e.attribute;return n===!1?void 0:typeof n=="string"?n:typeof t=="string"?t.toLowerCase():void 0}constructor(){super(),this._$Ep=void 0,this.isUpdatePending=!1,this.hasUpdated=!1,this._$Em=null,this._$Ev()}_$Ev(){this._$ES=new Promise(t=>this.enableUpdating=t),this._$AL=new Map,this._$E_(),this.requestUpdate(),this.constructor.l?.forEach(t=>t(this))}addController(t){(this._$EO??=new Set).add(t),this.renderRoot!==void 0&&this.isConnected&&t.hostConnected?.()}removeController(t){this._$EO?.delete(t)}_$E_(){let t=new Map,e=this.constructor.elementProperties;for(let n of e.keys())this.hasOwnProperty(n)&&(t.set(n,this[n]),delete this[n]);t.size>0&&(this._$Ep=t)}createRenderRoot(){let t=this.shadowRoot??this.attachShadow(this.constructor.shadowRootOptions);return Ut(t,this.constructor.elementStyles),t}connectedCallback(){this.renderRoot??=this.createRenderRoot(),this.enableUpdating(!0),this._$EO?.forEach(t=>t.hostConnected?.())}enableUpdating(t){}disconnectedCallback(){this._$EO?.forEach(t=>t.hostDisconnected?.())}attributeChangedCallback(t,e,n){this._$AK(t,n)}_$ET(t,e){let n=this.constructor.elementProperties.get(t),i=this.constructor._$Eu(t,n);if(i!==void 0&&n.reflect===!0){let s=(n.converter?.toAttribute!==void 0?n.converter:ht).toAttribute(e,n.type);this._$Em=t,s==null?this.removeAttribute(i):this.setAttribute(i,s),this._$Em=null}}_$AK(t,e){let n=this.constructor,i=n._$Eh.get(t);if(i!==void 0&&this._$Em!==i){let s=n.getPropertyOptions(i),r=typeof s.converter=="function"?{fromAttribute:s.converter}:s.converter?.fromAttribute!==void 0?s.converter:ht;this._$Em=i;let d=r.fromAttribute(e,s.type);this[i]=d??this._$Ej?.get(i)??d,this._$Em=null}}requestUpdate(t,e,n,i=!1,s){if(t!==void 0){let r=this.constructor;if(i===!1&&(s=this[t]),n??=r.getPropertyOptions(t),!((n.hasChanged??zt)(s,e)||n.useDefault&&n.reflect&&s===this._$Ej?.get(t)&&!this.hasAttribute(r._$Eu(t,n))))return;this.C(t,e,n)}this.isUpdatePending===!1&&(this._$ES=this._$EP())}C(t,e,{useDefault:n,reflect:i,wrapped:s},r){n&&!(this._$Ej??=new Map).has(t)&&(this._$Ej.set(t,r??e??this[t]),s!==!0||r!==void 0)||(this._$AL.has(t)||(this.hasUpdated||n||(e=void 0),this._$AL.set(t,e)),i===!0&&this._$Em!==t&&(this._$Eq??=new Set).add(t))}async _$EP(){this.isUpdatePending=!0;try{await this._$ES}catch(e){Promise.reject(e)}let t=this.scheduleUpdate();return t!=null&&await t,!this.isUpdatePending}scheduleUpdate(){return this.performUpdate()}performUpdate(){if(!this.isUpdatePending)return;if(!this.hasUpdated){if(this.renderRoot??=this.createRenderRoot(),this._$Ep){for(let[i,s]of this._$Ep)this[i]=s;this._$Ep=void 0}let n=this.constructor.elementProperties;if(n.size>0)for(let[i,s]of n){let{wrapped:r}=s,d=this[i];r!==!0||this._$AL.has(i)||d===void 0||this.C(i,void 0,s,d)}}let t=!1,e=this._$AL;try{t=this.shouldUpdate(e),t?(this.willUpdate(e),this._$EO?.forEach(n=>n.hostUpdate?.()),this.update(e)):this._$EM()}catch(n){throw t=!1,this._$EM(),n}t&&this._$AE(e)}willUpdate(t){}_$AE(t){this._$EO?.forEach(e=>e.hostUpdated?.()),this.hasUpdated||(this.hasUpdated=!0,this.firstUpdated(t)),this.updated(t)}_$EM(){this._$AL=new Map,this.isUpdatePending=!1}get updateComplete(){return this.getUpdateComplete()}getUpdateComplete(){return this._$ES}shouldUpdate(t){return!0}update(t){this._$Eq&&=this._$Eq.forEach(e=>this._$ET(e,this[e])),this._$EM()}updated(t){}firstUpdated(t){}};x.elementStyles=[],x.shadowRootOptions={mode:"open"},x[U("elementProperties")]=new Map,x[U("finalized")]=new Map,Fe?.({ReactiveElement:x}),(Z.reactiveElementVersions??=[]).push("2.1.2");var vt=globalThis,jt=o=>o,J=vt.trustedTypes,Vt=J?J.createPolicy("lit-html",{createHTML:o=>o}):void 0,Gt="$lit$",E=`lit$${Math.random().toFixed(9).slice(2)}$`,Yt="?"+E,Ke=`<${Yt}>`,T=document,I=()=>T.createComment(""),z=o=>o===null||typeof o!="object"&&typeof o!="function",$t=Array.isArray,We=o=>$t(o)||typeof o?.[Symbol.iterator]=="function",mt=`[ 	
\f\r]`,D=/<(?:(!--|\/[^a-zA-Z])|(\/?[a-zA-Z][^>\s]*)|(\/?$))/g,Bt=/-->/g,Ft=/>/g,S=RegExp(`>|${mt}(?:([^\\s"'>=/]+)(${mt}*=${mt}*(?:[^ 	
\f\r"'\`<>=]|("|')|))|$)`,"g"),Kt=/'/g,Wt=/"/g,Xt=/^(?:script|style|textarea|title)$/i,xt=o=>(t,...e)=>({_$litType$:o,strings:t,values:e}),p=xt(1),Tn=xt(2),Pn=xt(3),w=Symbol.for("lit-noChange"),c=Symbol.for("lit-nothing"),qt=new WeakMap,k=T.createTreeWalker(T,129);function Zt(o,t){if(!$t(o)||!o.hasOwnProperty("raw"))throw Error("invalid template strings array");return Vt!==void 0?Vt.createHTML(t):t}var qe=(o,t)=>{let e=o.length-1,n=[],i,s=t===2?"<svg>":t===3?"<math>":"",r=D;for(let d=0;d<e;d++){let a=o[d],h,m,u=-1,f=0;for(;f<a.length&&(r.lastIndex=f,m=r.exec(a),m!==null);)f=r.lastIndex,r===D?m[1]==="!--"?r=Bt:m[1]!==void 0?r=Ft:m[2]!==void 0?(Xt.test(m[2])&&(i=RegExp("</"+m[2],"g")),r=S):m[3]!==void 0&&(r=S):r===S?m[0]===">"?(r=i??D,u=-1):m[1]===void 0?u=-2:(u=r.lastIndex-m[2].length,h=m[1],r=m[3]===void 0?S:m[3]==='"'?Wt:Kt):r===Wt||r===Kt?r=S:r===Bt||r===Ft?r=D:(r=S,i=void 0);let g=r===S&&o[d+1].startsWith("/>")?" ":"";s+=r===D?a+Ke:u>=0?(n.push(h),a.slice(0,u)+Gt+a.slice(u)+E+g):a+E+(u===-2?d:g)}return[Zt(o,s+(o[e]||"<?>")+(t===2?"</svg>":t===3?"</math>":"")),n]},j=class o{constructor({strings:t,_$litType$:e},n){let i;this.parts=[];let s=0,r=0,d=t.length-1,a=this.parts,[h,m]=qe(t,e);if(this.el=o.createElement(h,n),k.currentNode=this.el.content,e===2||e===3){let u=this.el.content.firstChild;u.replaceWith(...u.childNodes)}for(;(i=k.nextNode())!==null&&a.length<d;){if(i.nodeType===1){if(i.hasAttributes())for(let u of i.getAttributeNames())if(u.endsWith(Gt)){let f=m[r++],g=i.getAttribute(u).split(E),C=/([.?@])?(.*)/.exec(f);a.push({type:1,index:s,name:C[2],strings:g,ctor:C[1]==="."?_t:C[1]==="?"?gt:C[1]==="@"?yt:H}),i.removeAttribute(u)}else u.startsWith(E)&&(a.push({type:6,index:s}),i.removeAttribute(u));if(Xt.test(i.tagName)){let u=i.textContent.split(E),f=u.length-1;if(f>0){i.textContent=J?J.emptyScript:"";for(let g=0;g<f;g++)i.append(u[g],I()),k.nextNode(),a.push({type:2,index:++s});i.append(u[f],I())}}}else if(i.nodeType===8)if(i.data===Yt)a.push({type:2,index:s});else{let u=-1;for(;(u=i.data.indexOf(E,u+1))!==-1;)a.push({type:7,index:s}),u+=E.length-1}s++}}static createElement(t,e){let n=T.createElement("template");return n.innerHTML=t,n}};function P(o,t,e=o,n){if(t===w)return t;let i=n!==void 0?e._$Co?.[n]:e._$Cl,s=z(t)?void 0:t._$litDirective$;return i?.constructor!==s&&(i?._$AO?.(!1),s===void 0?i=void 0:(i=new s(o),i._$AT(o,e,n)),n!==void 0?(e._$Co??=[])[n]=i:e._$Cl=i),i!==void 0&&(t=P(o,i._$AS(o,t.values),i,n)),t}var ft=class{constructor(t,e){this._$AV=[],this._$AN=void 0,this._$AD=t,this._$AM=e}get parentNode(){return this._$AM.parentNode}get _$AU(){return this._$AM._$AU}u(t){let{el:{content:e},parts:n}=this._$AD,i=(t?.creationScope??T).importNode(e,!0);k.currentNode=i;let s=k.nextNode(),r=0,d=0,a=n[0];for(;a!==void 0;){if(r===a.index){let h;a.type===2?h=new V(s,s.nextSibling,this,t):a.type===1?h=new a.ctor(s,a.name,a.strings,this,t):a.type===6&&(h=new bt(s,this,t)),this._$AV.push(h),a=n[++d]}r!==a?.index&&(s=k.nextNode(),r++)}return k.currentNode=T,i}p(t){let e=0;for(let n of this._$AV)n!==void 0&&(n.strings!==void 0?(n._$AI(t,n,e),e+=n.strings.length-2):n._$AI(t[e])),e++}},V=class o{get _$AU(){return this._$AM?._$AU??this._$Cv}constructor(t,e,n,i){this.type=2,this._$AH=c,this._$AN=void 0,this._$AA=t,this._$AB=e,this._$AM=n,this.options=i,this._$Cv=i?.isConnected??!0}get parentNode(){let t=this._$AA.parentNode,e=this._$AM;return e!==void 0&&t?.nodeType===11&&(t=e.parentNode),t}get startNode(){return this._$AA}get endNode(){return this._$AB}_$AI(t,e=this){t=P(this,t,e),z(t)?t===c||t==null||t===""?(this._$AH!==c&&this._$AR(),this._$AH=c):t!==this._$AH&&t!==w&&this._(t):t._$litType$!==void 0?this.$(t):t.nodeType!==void 0?this.T(t):We(t)?this.k(t):this._(t)}O(t){return this._$AA.parentNode.insertBefore(t,this._$AB)}T(t){this._$AH!==t&&(this._$AR(),this._$AH=this.O(t))}_(t){this._$AH!==c&&z(this._$AH)?this._$AA.nextSibling.data=t:this.T(T.createTextNode(t)),this._$AH=t}$(t){let{values:e,_$litType$:n}=t,i=typeof n=="number"?this._$AC(t):(n.el===void 0&&(n.el=j.createElement(Zt(n.h,n.h[0]),this.options)),n);if(this._$AH?._$AD===i)this._$AH.p(e);else{let s=new ft(i,this),r=s.u(this.options);s.p(e),this.T(r),this._$AH=s}}_$AC(t){let e=qt.get(t.strings);return e===void 0&&qt.set(t.strings,e=new j(t)),e}k(t){$t(this._$AH)||(this._$AH=[],this._$AR());let e=this._$AH,n,i=0;for(let s of t)i===e.length?e.push(n=new o(this.O(I()),this.O(I()),this,this.options)):n=e[i],n._$AI(s),i++;i<e.length&&(this._$AR(n&&n._$AB.nextSibling,i),e.length=i)}_$AR(t=this._$AA.nextSibling,e){for(this._$AP?.(!1,!0,e);t!==this._$AB;){let n=jt(t).nextSibling;jt(t).remove(),t=n}}setConnected(t){this._$AM===void 0&&(this._$Cv=t,this._$AP?.(t))}},H=class{get tagName(){return this.element.tagName}get _$AU(){return this._$AM._$AU}constructor(t,e,n,i,s){this.type=1,this._$AH=c,this._$AN=void 0,this.element=t,this.name=e,this._$AM=i,this.options=s,n.length>2||n[0]!==""||n[1]!==""?(this._$AH=Array(n.length-1).fill(new String),this.strings=n):this._$AH=c}_$AI(t,e=this,n,i){let s=this.strings,r=!1;if(s===void 0)t=P(this,t,e,0),r=!z(t)||t!==this._$AH&&t!==w,r&&(this._$AH=t);else{let d=t,a,h;for(t=s[0],a=0;a<s.length-1;a++)h=P(this,d[n+a],e,a),h===w&&(h=this._$AH[a]),r||=!z(h)||h!==this._$AH[a],h===c?t=c:t!==c&&(t+=(h??"")+s[a+1]),this._$AH[a]=h}r&&!i&&this.j(t)}j(t){t===c?this.element.removeAttribute(this.name):this.element.setAttribute(this.name,t??"")}},_t=class extends H{constructor(){super(...arguments),this.type=3}j(t){this.element[this.name]=t===c?void 0:t}},gt=class extends H{constructor(){super(...arguments),this.type=4}j(t){this.element.toggleAttribute(this.name,!!t&&t!==c)}},yt=class extends H{constructor(t,e,n,i,s){super(t,e,n,i,s),this.type=5}_$AI(t,e=this){if((t=P(this,t,e,0)??c)===w)return;let n=this._$AH,i=t===c&&n!==c||t.capture!==n.capture||t.once!==n.once||t.passive!==n.passive,s=t!==c&&(n===c||i);i&&this.element.removeEventListener(this.name,this,n),s&&this.element.addEventListener(this.name,this,t),this._$AH=t}handleEvent(t){typeof this._$AH=="function"?this._$AH.call(this.options?.host??this.element,t):this._$AH.handleEvent(t)}},bt=class{constructor(t,e,n){this.element=t,this.type=6,this._$AN=void 0,this._$AM=e,this.options=n}get _$AU(){return this._$AM._$AU}_$AI(t){P(this,t)}};var Ge=vt.litHtmlPolyfillSupport;Ge?.(j,V),(vt.litHtmlVersions??=[]).push("3.3.3");var Jt=(o,t,e)=>{let n=e?.renderBefore??t,i=n._$litPart$;if(i===void 0){let s=e?.renderBefore??null;n._$litPart$=i=new V(t.insertBefore(I(),s),s,void 0,e??{})}return i._$AI(o),i};var wt=globalThis,b=class extends x{constructor(){super(...arguments),this.renderOptions={host:this},this._$Do=void 0}createRenderRoot(){let t=super.createRenderRoot();return this.renderOptions.renderBefore??=t.firstChild,t}update(t){let e=this.render();this.hasUpdated||(this.renderOptions.isConnected=this.isConnected),super.update(t),this._$Do=Jt(e,this.renderRoot,this.renderOptions)}connectedCallback(){super.connectedCallback(),this._$Do?.setConnected(!0)}disconnectedCallback(){super.disconnectedCallback(),this._$Do?.setConnected(!1)}render(){return w}};b._$litElement$=!0,b.finalized=!0,wt.litElementHydrateSupport?.({LitElement:b});var Ye=wt.litElementPolyfillSupport;Ye?.({LitElement:b});(wt.litElementVersions??=[]).push("4.2.2");async function R(o,t,e,n,i){try{await o.callService(t,e,n,{entity_id:i})}catch{}}function B(o,t,e){return R(o,"number","set_value",{value:e},t)}function F(o,t,e){return R(o,"timerify","add_time",{minutes:e},t)}function At(o,t){return R(o,"timerify","run",{},t)}function Qt(o,t){return R(o,"timerify","stop",{},t)}function te(o,t,e){return R(o,"switch",e?"turn_on":"turn_off",{},t)}function ee(o,t,e){return R(o,"timerify","cancel_command",{command_id:e},t)}var ne={card_entity_not_found:"Entity not found: {entity}",card_not_a_timer:"{entity} is not the Run for number of a Timerify timer",card_timer_incomplete:"The timer of {entity} cannot be shown: its target or one of its sensors is missing. Open the timer's page to see why.",card_not_allowed:"You are not allowed to see the timer {entity}",card_ends_at_disabled:"The Ends at sensor of this timer, {sensor}, is disabled. Enable it for the card to work",card_error_entity:"Choose the Run for number of a timer",card_error_layout:"The layout is pill or round",card_error_presets:"Presets are whole minutes from 1 to 1440",card_error_chip:"The quick chip is whole minutes from 1 to 1440",card_error_press:"Tap, double tap and hold can each be popup, run, stop, run_or_stop, action or none",card_error_action:"A Home Assistant action is a set of settings, such as action: more-info",card_close:"Close",card_until:"until {time}",card_add_time:"Add {duration}",card_subtract_time:"Take off {duration}",card_stop:"Stop",card_schedule:"Schedule",card_commands:"Pending commands",card_commands_disabled:"Pending commands are hidden: the Next command sensor, {sensor}, is disabled",card_command_on:"On at {time}",card_command_on_for:"On at {time} for {duration}",card_command_off:"Off at {time}",card_cancel_command:"Cancel",card_settings:"Settings",card_picker_description:"The countdown, presets and schedule of a Timerify timer",card_editor_entity:"Timer",card_editor_layout:"Layout",card_editor_layout_pill:"Pill",card_editor_layout_round:"Round",card_editor_name:"Name",card_editor_icon:"Icon",card_editor_presets:"Duration presets (minutes)",card_editor_presets_helper:"Leave empty for {presets}",card_editor_chip:"Quick add chip (minutes, pill only)",card_editor_interactions:"Interactions",card_editor_tap:"Tap behavior",card_editor_double_tap:"Double tap behavior",card_editor_hold:"Hold behavior",card_editor_tap_action:"Tap action",card_editor_double_tap_action:"Double tap action",card_editor_hold_action:"Hold action",card_editor_press_popup:"Open the pop-up",card_editor_press_run:"Run for the default duration",card_editor_press_stop:"Stop",card_editor_press_run_or_stop:"Start or stop",card_editor_press_action:"Home Assistant action",card_editor_press_none:"Nothing",card_editor_action_helper:'Used when the behavior above is set to "Home Assistant action"'};var ie="common",se="timerify",Xe=`component.${se}.${ie}.`;function Et(o){return Xe+o}function Ze(o,t){return o.replace(/\{(\w+)\}/g,(e,n)=>String(t?.[n]??e))}function l(o,t,e){return o?.localize(Et(t),e)||Ze(ne[t],e)}var K,oe=Promise.resolve(),re,ae=new Set;function Q(o){return o.language!==K&&(K=o.language,oe=Je(o,o.language)),oe}async function Je(o,t){let e;try{e=await o.loadBackendTranslation(ie,se)}catch{K===t&&(K=void 0);return}K===t&&(re={...o,localize:e},ae.forEach(n=>n()))}function A(){return re}function de(o){ae.add(o)}var W=[15,30,45,60,120],St=1440,kt=["popup","run","stop","run_or_stop","action","none"],Qe=["tap","double_tap","hold"],Tt=["tap_action","double_tap_action","hold_action"],_=class extends Error{constructor(e){super(l(A(),e));this.key=e}key};function le(o){let t=typeof o=="number"?o:typeof o=="string"&&/^\d+$/.test(o)?Number(o):void 0;return t!==void 0&&Number.isInteger(t)&&t>=1&&t<=St?t:void 0}function tn(o){if(o===void 0||Array.isArray(o)&&o.length===0)return[...W];if(!Array.isArray(o))throw new _("card_error_presets");let t=new Set;for(let e of o){let n=le(e);if(n===void 0)throw new _("card_error_presets");t.add(n)}return[...t]}function en(o){if(o===void 0)return;let t=le(o);if(t===void 0)throw new _("card_error_chip");return t}var ue=o=>typeof o=="object"&&o!==null?o:{},nn=o=>kt.some(t=>t===o);function Ct(o,t){if(o===void 0)return t;if(!nn(o))throw new _("card_error_press");return o}var on=o=>typeof o=="object"&&o!==null&&!Array.isArray(o);function pe(o){let t={};for(let e of Tt){let n=o[e];if(n!==void 0){if(!on(n))throw new _("card_error_action");t[e]=n}}return t}var ce=o=>typeof o=="number"||typeof o=="string";function he(o){let t=ue(o),{entity:e,layout:n,presets:i,chip:s}=t;if(e!==void 0&&typeof e!="string")throw new _("card_error_entity");if(n!==void 0&&typeof n!="string")throw new _("card_error_layout");if(i!==void 0&&!(Array.isArray(i)&&i.every(ce)))throw new _("card_error_presets");if(s!==void 0&&!ce(s))throw new _("card_error_chip");for(let r of Qe)if(t[r]!==void 0&&typeof t[r]!="string")throw new _("card_error_press");pe(t)}function me(o){let t=ue(o),{entity:e,layout:n="pill",name:i,icon:s}=t;if(typeof e!="string"||!/^number\.[a-z0-9_]+$/.test(e))throw new _("card_error_entity");if(n!=="pill"&&n!=="round")throw new _("card_error_layout");let r=en(t.chip);return{entity:e,layout:n,...typeof i=="string"&&i!==""&&{name:i},...typeof s=="string"&&s!==""&&{icon:s},presets:tn(t.presets),...r!==void 0&&{chip:r},tap:Ct(t.tap,"popup"),double_tap:Ct(t.double_tap,"none"),hold:Ct(t.hold,n==="round"?"run_or_stop":"none"),...pe(t)}}var tt=class{#t;#e;#n;#o=!1;#i;constructor(t,e,n){this.#t=t,this.#e=e,this.#n=n,t.addController(this)}hostConnected(){this.#o=!0,this.#r()}hostUpdated(){this.#r()}hostDisconnected(){this.#o=!1,this.#r()}#r(){let t=this.#e(),e=this.#o&&t!==void 0&&t.getTime()>this.#n();e&&this.#i===void 0?this.#i=setInterval(()=>this.#t.requestUpdate(),1e3):!e&&this.#i!==void 0&&(clearInterval(this.#i),this.#i=void 0)}};var fe=o=>String(o).padStart(2,"0");function O(o){let t=Math.ceil(Math.max(0,o)),e=Math.floor(t/3600),n=Math.floor(t%3600/60),i=fe(t%60);return e>0?`${e}:${fe(n)}:${i}`:`${n}:${i}`}function sn({language:o,time_format:t}){if(t==="12"||t==="24")return t==="12";let e=new Intl.DateTimeFormat(t==="language"?o:void 0,{hour:"numeric"}).resolvedOptions();return e.hourCycle==="h11"||e.hourCycle==="h12"}var rn=864e5;function _e(o,t){let e=new Intl.DateTimeFormat("en-US",{timeZone:o,year:"numeric",month:"numeric",day:"numeric"}).formatToParts(t),n=i=>Number(e.find(s=>s.type===i)?.value);return Date.UTC(n("year"),n("month")-1,n("day"))/rn}function q(o,t,e){let{locale:n}=o,i=n.time_zone==="server"?o.config.time_zone:void 0,s=_e(i,t.getTime())-_e(i,e),r=s===0?{}:s>=1&&s<=6?{weekday:"short"}:{month:"short",day:"numeric"};return new Intl.DateTimeFormat(n.language,{...r,hour:"numeric",minute:"2-digit",hourCycle:sn(n)?"h12":"h23",timeZone:i}).format(t)}function v(o,t){let e=(r,d)=>new Intl.NumberFormat(o.locale.language,{style:"unit",unit:d,unitDisplay:"short",useGrouping:!1}).format(r),n=Math.floor(t/60),i=t%60,s=n>0?[e(n,"hour")]:[];return(i>0||n===0)&&s.push(e(i,"minute")),s.join(" ")}function ge(o,t,e,n,i){return e.includes(n)&&typeof i=="number"?new Intl.NumberFormat(o.locale.language,{style:"percent",maximumFractionDigits:1}).format(i/100):t===void 0?String(i):n==="hvac_mode"?o.formatEntityState(t,String(i)):o.formatEntityAttributeValue(t,n,i)}var ye={entity:"card_editor_entity",layout:"card_editor_layout",name:"card_editor_name",icon:"card_editor_icon",presets:"card_editor_presets",chip:"card_editor_chip",interactions:"card_editor_interactions",tap:"card_editor_tap",double_tap:"card_editor_double_tap",hold:"card_editor_hold",tap_action:"card_editor_tap_action",double_tap_action:"card_editor_double_tap_action",hold_action:"card_editor_hold_action"},an={popup:"card_editor_press_popup",run:"card_editor_press_run",stop:"card_editor_press_stop",run_or_stop:"card_editor_press_run_or_stop",action:"card_editor_press_action",none:"card_editor_press_none"},dn=o=>Object.hasOwn(ye,o),cn=o=>o.endsWith("_action"),ln={locale:{language:"en"}};function be(){return A()??ln}function un(){let o=be();return new Intl.ListFormat(o.locale.language,{style:"long",type:"conjunction"}).format(W.map(t=>v(o,t)))}async function ve(){let o=A(),t=kt.map(e=>({value:e,label:l(o,an[e])}));return{schema:[{name:"entity",required:!0,selector:{entity:{filter:{integration:"timerify",domain:"number"}}}},{name:"layout",selector:{select:{options:[{value:"pill",label:l(o,"card_editor_layout_pill")},{value:"round",label:l(o,"card_editor_layout_round")}]}}},{name:"",type:"grid",schema:[{name:"name",selector:{text:{}}},{name:"icon",selector:{icon:{}}}]},{name:"presets",selector:{select:{multiple:!0,custom_value:!0,options:W.map(e=>({value:String(e),label:v(be(),e)}))}}},{name:"chip",selector:{number:{min:1,max:St,mode:"box"}}},{name:"interactions",type:"expandable",flatten:!0,icon:"mdi:gesture-tap",schema:[{name:"tap",selector:{select:{options:t}}},{name:"tap_action",selector:{ui_action:{default_action:"more-info"}}},{name:"double_tap",selector:{select:{options:t}}},{name:"double_tap_action",selector:{ui_action:{default_action:"more-info"}}},{name:"hold",selector:{select:{options:t}}},{name:"hold_action",selector:{ui_action:{default_action:"more-info"}}}]}],assertConfig:he,computeLabel:({name:e},n)=>dn(e)?n(Et(ye[e])):"",computeHelper:({name:e})=>e==="presets"?l(A(),"card_editor_presets_helper",{presets:un()}):cn(e)?l(A(),"card_editor_action_helper"):void 0}}function $e(o,t,e){Q(o);let n=s=>{let r=o.entities[s];return r?.platform==="timerify"&&r.translation_key==="run_for"},i=s=>s.filter(n).sort()[0];return{entity:i(t)??i(e)??i(Object.keys(o.entities))??"",layout:"pill",presets:W.map(String)}}var pn="not_found",hn="timer_incomplete",mn="unauthorized";async function we(o,t){let e=Date.now();try{let n=await o.callWS({type:"timerify/timer",entity_id:t}),i=Pt(n.server_time),s=i===void 0?0:i-(e+Date.now())/2;return{status:"found",info:n,clockOffset:s}}catch(n){let i=typeof n=="object"&&n!==null&&"code"in n?n.code:"";return i===pn?{status:"not_found"}:i===hn?{status:"incomplete"}:{status:i===mn?"unauthorized":"failed"}}}var G=o=>Date.now()+(o.status==="found"?o.clockOffset:0),et=(o,t)=>o.disabled_sensors.includes(t),M=o=>o!==void 0&&o.state!=="unavailable"&&o.state!=="unknown";function fn(o,t){return o===void 0||o.state==="unavailable"||o.state==="unknown"?!1:t.states.includes(o.state)===(t.match==="is")}var _n="mdi:timer-outline",xe=o=>o===void 0||o.state==="unavailable";function Pt(o){let t=typeof o=="string"?Date.parse(o):Number.NaN;return Number.isNaN(t)?void 0:t}function Ae(o,t,e,n){let i=e.status==="found"?e.info:void 0,s=o.states[t.entity],r=i&&o.states[i.target],d=t.name||r&&o.formatEntityName(r,void 0)||s?.attributes.friendly_name||t.entity,a=t.icon?{icon:t.icon}:r?{stateObj:r}:{icon:_n},h={name:d,icon:a,target:r,remaining:0},m=i&&o.states[i.ends_at];if(i===void 0||m===void 0||xe(s)||xe(m))return{...h,state:"unavailable",progress:0};let u=Pt(m.state);if(u===void 0)return fn(r,i.target_on)?{...h,state:"open",progress:1}:{...h,state:"idle",progress:0};let f=Pt(m.attributes.started_at),g=f===void 0?0:(u-f)/1e3,C=Math.max(0,(u-n)/1e3);return{...h,state:"counting",remaining:C,progress:g>0?Math.min(1,C/g):1,endsAt:new Date(u)}}function nt(o,t){return t?[o,t.ends_at,t.next_command,t.target,...t.intervals.map(({entity_id:e})=>e)]:[o]}var gn=["locale","language","localize","config","user","connected","entities","formatEntityName","formatEntityState","formatEntityAttributeValue"];function ot(o,t,e){for(let i of o.keys())if(i!=="hass")return!0;let n=o.get("hass");return n===void 0||t===void 0?!0:gn.some(i=>n[i]!==t[i])||e.some(i=>n.states[i]!==t.states[i])}function it(o){return"stateObj"in o.icon?p`<ha-state-icon .stateObj=${o.icon.stateObj}></ha-state-icon>`:p`<ha-icon .icon=${o.icon.icon}></ha-icon>`}var st=o=>o.tap==="popup"?"dialog":void 0,rt=o=>o.tap!=="none"||o.double_tap!=="none"||o.hold!=="none";function yn(o,t,e){if(o.state!=="unavailable")return o.target?e.formatEntityState(o.target):"";let n=e.states[t.entity];if(M(n))return"";let i={entity_id:t.entity,state:"unavailable",attributes:{}};return e.formatEntityState(n??i,"unavailable")}function at(o,t,e,n){if(o.state!=="counting"||o.endsAt===void 0)return yn(o,t,e);let i=q(e,o.endsAt,n);return p`
    <span class="remaining">${O(o.remaining)}</span>
    <span class="until">${l(e,"card_until",{time:i})}</span>
  `}var Ee=y`
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
    /* No flash of the browser's own highlight on a tap, as in the tile card. */
    -webkit-tap-highlight-color: transparent;
  }
  .body[role="button"] {
    cursor: pointer;
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
  /* What a layout shows while letting go of a long press would act: it pulses. */
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
`;var $=o=>o??c;var Ce={ATTRIBUTE:1,CHILD:2,PROPERTY:3,BOOLEAN_ATTRIBUTE:4,EVENT:5,ELEMENT:6},Se=o=>(...t)=>({_$litDirective$:o,values:t}),dt=class{constructor(t){}get _$AU(){return this._$AM._$AU}_$AT(t,e,n){this._$Ct=t,this._$AM=e,this._$Ci=n}_$AS(t,e){return this.update(t,e)}update(t,e){return this.render(...e)}};var ke="important",bn=" !"+ke,Te=Se(class extends dt{constructor(o){if(super(o),o.type!==Ce.ATTRIBUTE||o.name!=="style"||o.strings?.length>2)throw Error("The `styleMap` directive must be used in the `style` attribute and must be the only part in the attribute.")}render(o){return Object.keys(o).reduce((t,e)=>{let n=o[e];return n==null?t:t+`${e=e.includes("-")?e:e.replace(/(?:^(webkit|moz|ms|o)|)(?=[A-Z])/g,"-$&").toLowerCase()}:${n};`},"")}update(o,[t]){let{style:e}=o.element;if(this.ft===void 0)return this.ft=new Set(Object.keys(t)),this.render(t);for(let n of this.ft)t[n]==null&&(this.ft.delete(n),n.includes("-")?e.removeProperty(n):e[n]=null);for(let n in t){let i=t[n];if(i!=null){this.ft.add(n);let s=typeof i=="string"&&i.endsWith(bn);n.includes("-")||s?e.setProperty(n,s?i.slice(0,-11):i,s?ke:""):e[n]=i}}return w}});function Pe(o,t,e,n,i,s){let r=Math.round(o.progress*1e3)/10,d=rt(t);return p`
    <ha-card class="pill ${o.state}">
      <div
        class="body"
        role=${$(d?"button":void 0)}
        tabindex=${$(d?"0":void 0)}
        aria-haspopup=${$(st(t))}
        aria-labelledby=${$(d?"label":void 0)}
        @click=${n.click}
        @keydown=${n.keydown}
        @keyup=${n.keyup}
        @pointerdown=${n.pointerdown}
        @pointerup=${n.pointerup}
        @pointercancel=${n.pointercancel}
        @pointerleave=${n.pointerleave}
        @contextmenu=${n.contextmenu}
      >
        <span class="fill-clip" aria-hidden="true">
          <span class="fill" style=${Te({width:`${r}%`})}></span>
        </span>
      </div>
      <div class="content">
        <span class="icon">${it(o)}</span>
        <span class="text" id="label">
          <span class="name">${o.name}</span>
          <span class="status">${at(o,t,e,s)}</span>
        </span>
        ${t.chip===void 0?c:p`
              <button
                class="chip"
                type="button"
                aria-label=${l(e,"card_add_time",{duration:v(e,t.chip)})}
                ?disabled=${o.state==="unavailable"}
                @click=${i}
              >
                +${v(e,t.chip)}
              </button>
            `}
      </div>
    </ha-card>
  `}var He=y`
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
  /*
   * The pill has a long press only when the config gives it one. While letting go would act,
   * the icon pulses, as the round tile's ring does; a timer that is unavailable stays still.
   */
  :host([data-held]) .pill:not(.unavailable) .icon {
    animation: pulse 0.8s ease-in-out infinite alternate;
  }
  @media (prefers-reduced-motion: reduce) {
    :host([data-held]) .pill:not(.unavailable) .icon {
      animation: none;
      transform: scale(1.08);
    }
  }
`;function vn(o,t){let e=t?.attributes.max;return typeof e=="number"&&Number.isFinite(e)?o.filter(n=>n<=e):[...o]}function $n(o){let t=o?.attributes.commands;return Array.isArray(t)?t.flatMap(e=>{if(typeof e!="object"||e===null)return[];let{id:n,at:i,action:s,minutes:r,settings:d}=e,a=typeof i=="string"?new Date(i):void 0;return typeof n!="string"||a===void 0||Number.isNaN(a.getTime())||s!=="on"&&s!=="off"?[]:[{id:n,at:a,action:s,minutes:typeof r=="number"&&r>0?r:null,settings:typeof d=="object"&&d!==null?Object.entries(d):[]}]}):[]}var xn=o=>`/config/integrations/integration/timerify#config_entry=${encodeURIComponent(o)}`,ct=class extends b{static properties={hass:{attribute:!1},config:{attribute:!1},lookup:{attribute:!1},view:{attribute:!1},opened:{state:!0}};static styles=y`
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
  `;constructor(){super(),this.opened=!1}open(){this.opened=!0}close(){this.#t?.close(),this.#s()}disconnectedCallback(){super.disconnectedCallback(),this.close()}get#t(){return this.renderRoot.querySelector("dialog")}#e=()=>{this.#t?.open||this.#s()};#n=!1;#o=t=>{this.#n=t.target===t.currentTarget};#i=t=>{this.#n&&=t.target===t.currentTarget};#r=()=>{this.#n=!1};#a=t=>{let e=this.#n&&t.target===t.currentTarget;this.#n=!1,e&&this.close()};#s(){this.opened&&(this.opened=!1,this.dispatchEvent(new CustomEvent("closed")))}shouldUpdate(t){if(!this.hasUpdated||t.has("opened"))return!0;let e=nt(this.config.entity,this.lookup.info);return this.opened&&ot(t,this.hass,e)}updated(t){let e=this.#t;t.has("opened")&&this.opened&&e&&!e.open&&e.showModal()}render(){return p`
      <dialog
        aria-labelledby="title"
        @cancel=${()=>this.close()}
        @close=${this.#e}
        @pointerdown=${this.#o}
        @pointerup=${this.#i}
        @pointercancel=${this.#r}
        @click=${this.#a}
      >
        ${this.opened?this.#c():c}
      </dialog>
    `}#c(){let{hass:t,view:e}=this,n=G(this.lookup);return p`
      <div class="wrapper">
        <header>
          <h2 id="title">${e.name}</h2>
          <button class="close" @click=${()=>this.close()}>${l(t,"card_close")}</button>
        </header>
        ${this.#p(n)} ${this.#l()} ${this.#h()} ${this.#d(n)}
        ${this.#f()}
      </div>
    `}#p(t){let{hass:e,view:n}=this;if(n.state!=="counting"||n.endsAt===void 0)return c;let i=q(e,n.endsAt,t);return p`
      <p class="countdown">
        <span class="remaining">${O(n.remaining)}</span>
        <span class="until">${l(e,"card_until",{time:i})}</span>
      </p>
    `}#l(){let{hass:t,config:e,view:n}=this,i=v(t,5),s=n.state==="counting",r=s||n.state==="open",d=n.state==="unavailable",a=vn(e.presets,t.states[e.entity]);return p`
      ${a.length===0?c:p`
            <div class="presets">
              ${a.map(h=>p`
                  <button
                    class="action preset"
                    ?disabled=${d}
                    @click=${()=>{B(t,e.entity,h)}}
                  >
                    ${v(t,h)}
                  </button>
                `)}
            </div>
          `}
      <div class="adjust">
        <button
          class="action step"
          aria-label=${l(t,"card_subtract_time",{duration:i})}
          ?disabled=${!s}
          @click=${()=>{F(t,e.entity,-5)}}
        >
          −${i}
        </button>
        <button
          class="action step"
          aria-label=${l(t,"card_add_time",{duration:i})}
          ?disabled=${d}
          @click=${()=>{F(t,e.entity,5)}}
        >
          +${i}
        </button>
        <button
          class="action stop"
          ?disabled=${!r}
          @click=${()=>{B(t,e.entity,0)}}
        >
          ${l(t,"card_stop")}
        </button>
      </div>
    `}#h(){let{intervals:t}=this.lookup.info;return t.length===0?c:p`
      <section class="schedule">
        <h3>${l(this.hass,"card_schedule")}</h3>
        <ul>
          ${t.map(e=>p`<li>${this.#u(e)}</li>`)}
        </ul>
      </section>
    `}#u({entity_id:t,title:e}){let{hass:n}=this,i=n.states[t],s=i!==void 0&&i.state!=="unavailable",r=s&&i.state==="on",d=i??{entity_id:t,state:"unavailable",attributes:{}};return p`
      <button
        class="interval"
        role="switch"
        aria-checked=${r?"true":"false"}
        ?disabled=${!s}
        @click=${()=>{te(n,t,!r)}}
      >
        <span class="label">
          <span class="title">${e}</span>
          ${s?c:p`<span class="state">${n.formatEntityState(d,"unavailable")}</span>`}
        </span>
        <span class="track" aria-hidden="true"><span class="knob"></span></span>
      </button>
    `}#d(t){let{hass:e,config:n,view:i}=this,{info:s}=this.lookup;if(et(s,s.next_command))return p`
        <section class="commands">
          <p class="note">${l(e,"card_commands_disabled",{sensor:s.next_command})}</p>
        </section>
      `;let r=$n(e.states[s.next_command]);if(r.length===0)return c;let d=i.state==="unavailable";return p`
      <section class="commands">
        <h3>${l(e,"card_commands")}</h3>
        <ul>
          ${r.map((a,h)=>{let m=a.settings.map(([u,f])=>ge(e,i.target,s.percent_settings,u,f));return p`
              <li>
                <div class="command" id="command-${h}">
                  <span class="what">${this.#m(a,t)}</span>
                  ${m.length===0?c:p`<span class="settings">${m.join(", ")}</span>`}
                </div>
                <button
                  class="cancel"
                  aria-label=${l(e,"card_cancel_command")}
                  aria-describedby="command-${h}"
                  ?disabled=${d}
                  @click=${()=>{ee(e,n.entity,a.id)}}
                >
                  <span aria-hidden="true">×</span>
                </button>
              </li>
            `})}
        </ul>
      </section>
    `}#m(t,e){let{hass:n}=this,i=q(n,t.at,e);return t.action==="off"?l(n,"card_command_off",{time:i}):t.minutes===null?l(n,"card_command_on",{time:i}):l(n,"card_command_on_for",{time:i,duration:v(n,t.minutes)})}#f(){return this.hass.user?.is_admin?p`
      <footer>
        <a href=${xn(this.lookup.info.entry_id)} @click=${this.#_}>
          ${l(this.hass,"card_settings")}
        </a>
      </footer>
    `:c}#_=t=>{!t.ctrlKey&&!t.metaKey&&!t.shiftKey&&this.close()}};var Re="data-held",lt=class{#t;#e;#n=!1;#o;#i;#r=!1;#a=!1;#s;#c=t=>this.#u(t);constructor(t,e){this.#t=t,this.#e=e,t.addController(this)}hostDisconnected(){this.#n=!1,this.#a=!1,this.#l(),this.#d()}cancelPress(){this.#d()}binding(){return{click:t=>{if(this.#a){this.#a=!1,t.preventDefault(),t.stopPropagation();return}this.#p()},keydown:t=>{t.key==="Enter"?(t.preventDefault(),t.repeat||this.#e().tap()):t.key===" "&&(t.preventDefault(),this.#n=!0)},keyup:t=>{if(t.key!==" ")return;let e=this.#n;this.#n=!1,e&&this.#e().tap()},pointerdown:t=>this.#h(t),pointerup:t=>{if(t.pointerId!==this.#o)return;let e=this.#r;this.#d();let{hold:n}=this.#e();e&&n!==void 0&&(this.#a=!0,n())},pointercancel:t=>this.#u(t),pointerleave:t=>this.#u(t),contextmenu:t=>{this.#o!==void 0&&t.preventDefault()}}}#p(){let{tap:t,doubleTap:e}=this.#e(),n=this.#s!==void 0;this.#l(),e===void 0?t():n?e():this.#s=setTimeout(()=>{this.#s=void 0,this.#e().tap()},250)}#l(){clearTimeout(this.#s),this.#s=void 0}#h(t){this.#e().hold===void 0||!t.isPrimary||t.button!==0||(this.#a=!1,this.#d(),this.#o=t.pointerId,window.addEventListener("pointerup",this.#c),window.addEventListener("pointercancel",this.#c),this.#i=setTimeout(()=>{this.#i=void 0,this.#r=!0,this.#t.setAttribute(Re,"")},500))}#u(t){t.pointerId===this.#o&&this.#d()}#d(){clearTimeout(this.#i),this.#i=void 0,this.#o=void 0,this.#r=!1,window.removeEventListener("pointerup",this.#c),window.removeEventListener("pointercancel",this.#c),this.#t.removeAttribute(Re)}};var L=80,Me=6,Rt=(L-Me)/2,Oe=2*Math.PI*Rt;function wn(o){if(o.state!=="counting")return p`<span class="icon">${it(o)}</span>`;let t=O(o.remaining);return p`<span class="time" aria-hidden="true">${t}</span>`}function Le(o,t,e,n,i){let s=L/2,r=rt(t);return p`
    <ha-card class="round ${o.state}">
      <div
        class="body"
        role=${$(r?"button":void 0)}
        tabindex=${$(r?"0":void 0)}
        aria-haspopup=${$(st(t))}
        aria-labelledby=${$(r?"label":void 0)}
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
          <svg class="ring" viewBox="0 0 ${L} ${L}" aria-hidden="true">
            <circle class="track" cx=${s} cy=${s} r=${Rt}></circle>
            <circle
              class="progress"
              cx=${s}
              cy=${s}
              r=${Rt}
              transform="rotate(-90 ${s} ${s})"
              stroke-dasharray=${Oe}
              stroke-dashoffset=${(1-o.progress)*Oe}
            ></circle>
          </svg>
          <span class="centre">
            ${wn(o)}
          </span>
        </div>
        <span class="text" id="label">
          <span class="name">${o.name}</span>
          <span class="status">${at(o,t,e,i)}</span>
        </span>
      </div>
    </ha-card>
  `}var Ne=y`
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
    width: ${L}px;
    height: ${L}px;
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
    stroke-width: ${Me};
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
  :host([data-held]) .round:not(.unavailable) .ring {
    animation: pulse 0.8s ease-in-out infinite alternate;
  }
  @media (prefers-reduced-motion: reduce) {
    :host([data-held]) .round:not(.unavailable) .ring {
      animation: none;
      transform: scale(1.08);
    }
  }
`;var Ot="timerify-card",An={pill:{columns:6,rows:1,min_columns:3,min_rows:1,max_rows:1},round:{columns:3,rows:2,min_columns:2,min_rows:2,max_rows:3}},Mt=class extends b{static properties={hass:{attribute:!1,noAccessor:!0},_config:{state:!0},_lookup:{state:!0}};static styles=[Ee,He,Ne,y`
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
    `];static getConfigForm=ve;static getStubConfig=$e;#t;#e=new Set;#n=!1;#o=!1;#i=new lt(this,()=>this.#d());#r=this.#i.binding();#a=()=>{let{_config:t,hass:e}=this;t?.chip!==void 0&&e!==void 0&&F(e,t.entity,t.chip)};#s;constructor(){super(),this._lookup={status:"pending"},new tt(this,()=>this.#s?.endsAt,()=>G(this._lookup))}get hass(){return this.#t}set hass(t){let e=this.#t;this.#t=t,this.requestUpdate("hass",e),this.#c(e,t)}setConfig(t){let e=me(t),n=this._config?.entity!==e.entity;this._config=e,n&&(this._lookup={status:"pending"},this.#l())}getCardSize(){return this._config?.layout==="round"?3:1}getGridOptions(){return An[this._config?.layout??"pill"]}async getUpdateComplete(){let t=await super.getUpdateComplete();for(;this.#e.size>0;)await Promise.allSettled([...this.#e]),t=await super.getUpdateComplete();return t}#c(t,e){let n=t!==void 0&&e.connected&&!t.connected;(t===void 0||t.language!==e.language||n)&&this.#p(Q(e));let i=this._config?.entity;i!==void 0&&(t===void 0||t.entities!==e.entities||n||M(e.states[i])&&!M(t.states[i]))&&this.#l()}#p(t){let e=t.finally(()=>this.#e.delete(e));this.#e.add(e)}#l(){if(this.#n){this.#o=!0;return}this.#n=!0,this.#p(this.#h())}async#h(){try{do{this.#o=!1;let t=this._config?.entity;if(this.#t===void 0||t===void 0)return;let e=await we(this.#t,t);this.#o||(this._lookup=e)}while(this.#o)}finally{this.#n=!1}}shouldUpdate(t){let e=this._lookup.status==="found"?this._lookup.info:void 0,n=this._config?nt(this._config.entity,e):[];return ot(t,this.#t,n)}get#u(){return this.renderRoot.querySelector("timerify-card-popup")}#d(){let t=this._config,e={tap:()=>this.#m("tap")};return t!==void 0&&t.double_tap!=="none"&&(e.doubleTap=()=>this.#m("double_tap")),t!==void 0&&t.hold!=="none"&&(e.hold=()=>this.#m("hold")),e}#m(t){let{_config:e,hass:n}=this;if(!(e===void 0||n===void 0))switch(e[t]){case"popup":this.#i.cancelPress(),this.#u?.open();break;case"run":At(n,e.entity);break;case"stop":Qt(n,e.entity);break;case"run_or_stop":this.#f(n,e);break;case"action":this.#_(t,e);break;case"none":break}}#f(t,e){let n=this.#s?.state;n==="counting"||n==="open"?B(t,e.entity,0):n==="idle"&&At(t,e.entity)}#_(t,e){if(this._lookup.status!=="found")return;let n=Object.fromEntries(Tt.filter(i=>e[i]!==void 0).map(i=>[i,e[i]]));this.dispatchEvent(new CustomEvent("hass-action",{detail:{config:{entity:this._lookup.info.target,...n},action:t},bubbles:!0,composed:!0}))}#g(t,e){let n=this._lookup;if(n.status==="unauthorized")return l(t,"card_not_allowed",{entity:e.entity});if(n.status==="incomplete")return l(t,"card_timer_incomplete",{entity:e.entity});if(n.status==="found"&&et(n.info,n.info.ends_at))return l(t,"card_ends_at_disabled",{sensor:n.info.ends_at});if(n.status!=="not_found")return;let i=t.states[e.entity];return i===void 0?l(t,"card_entity_not_found",{entity:e.entity}):M(i)?l(t,"card_not_a_timer",{entity:e.entity}):void 0}render(){let t=this.#t,e=this._config;if(!t||!e)return c;let n=this.#g(t,e);if(n)return this.#s=void 0,p`
        <ha-card>
          <div class="warning" role="alert">
            <ha-icon icon="mdi:alert-outline"></ha-icon>
            <span>${n}</span>
          </div>
        </ha-card>
      `;let i=G(this._lookup),s=Ae(t,e,this._lookup,i);return this.#s=s,p`
      ${e.layout==="round"?Le(s,e,t,this.#r,i):Pe(s,e,t,this.#r,this.#a,i)}
      ${this._lookup.status==="found"?p`
            <timerify-card-popup
              .hass=${t}
              .config=${e}
              .lookup=${this._lookup}
              .view=${s}
              @closed=${()=>this.renderRoot.querySelector(".body")?.focus()}
            ></timerify-card-popup>
          `:c}
    `}};if(!customElements.get(Ot)){customElements.define("timerify-card-popup",ct),customElements.define(Ot,Mt);let o={type:Ot,name:"Timerify",description:l(void 0,"card_picker_description"),preview:!0,documentationURL:"https://github.com/klimofey/timerify#dashboard-card"};(window.customCards??=[]).push(o),de(()=>{o.description=l(A(),"card_picker_description")})}export{Mt as TimerifyCard};
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

lit-html/directives/if-defined.js:
lit-html/directives/style-map.js:
  (**
   * @license
   * Copyright 2018 Google LLC
   * SPDX-License-Identifier: BSD-3-Clause
   *)
*/
