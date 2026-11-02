var J=globalThis,Q=J.ShadowRoot&&(J.ShadyCSS===void 0||J.ShadyCSS.nativeShadow)&&"adoptedStyleSheets"in Document.prototype&&"replace"in CSSStyleSheet.prototype,ft=Symbol(),Dt=new WeakMap,I=class{constructor(t,e,n){if(this._$cssResult$=!0,n!==ft)throw Error("CSSResult is not constructable. Use `unsafeCSS` or `css` instead.");this.cssText=t,this.t=e}get styleSheet(){let t=this.o,e=this.t;if(Q&&t===void 0){let n=e!==void 0&&e.length===1;n&&(t=Dt.get(e)),t===void 0&&((this.o=t=new CSSStyleSheet).replaceSync(this.cssText),n&&Dt.set(e,t))}return t}toString(){return this.cssText}},It=o=>new I(typeof o=="string"?o:o+"",void 0,ft),y=(o,...t)=>{let e=o.length===1?o[0]:t.reduce((n,i,r)=>n+(s=>{if(s._$cssResult$===!0)return s.cssText;if(typeof s=="number")return s;throw Error("Value passed to 'css' function must be a 'css' function result: "+s+". Use 'unsafeCSS' to pass non-literal values, but take care to ensure page security.")})(i)+o[r+1],o[0]);return new I(e,o,ft)},zt=(o,t)=>{if(Q)o.adoptedStyleSheets=t.map(e=>e instanceof CSSStyleSheet?e:e.styleSheet);else for(let e of t){let n=document.createElement("style"),i=J.litNonce;i!==void 0&&n.setAttribute("nonce",i),n.textContent=e.cssText,o.appendChild(n)}},mt=Q?o=>o:o=>o instanceof CSSStyleSheet?(t=>{let e="";for(let n of t.cssRules)e+=n.cssText;return It(e)})(o):o;var{is:ze,defineProperty:je,getOwnPropertyDescriptor:Ve,getOwnPropertyNames:Be,getOwnPropertySymbols:Fe,getPrototypeOf:Ke}=Object,tt=globalThis,jt=tt.trustedTypes,We=jt?jt.emptyScript:"",qe=tt.reactiveElementPolyfillSupport,z=(o,t)=>o,_t={toAttribute(o,t){switch(t){case Boolean:o=o?We:null;break;case Object:case Array:o=o==null?o:JSON.stringify(o)}return o},fromAttribute(o,t){let e=o;switch(t){case Boolean:e=o!==null;break;case Number:e=o===null?null:Number(o);break;case Object:case Array:try{e=JSON.parse(o)}catch{e=null}}return e}},Bt=(o,t)=>!ze(o,t),Vt={attribute:!0,type:String,converter:_t,reflect:!1,useDefault:!1,hasChanged:Bt};Symbol.metadata??=Symbol("metadata"),tt.litPropertyMetadata??=new WeakMap;var w=class extends HTMLElement{static addInitializer(t){this._$Ei(),(this.l??=[]).push(t)}static get observedAttributes(){return this.finalize(),this._$Eh&&[...this._$Eh.keys()]}static createProperty(t,e=Vt){if(e.state&&(e.attribute=!1),this._$Ei(),this.prototype.hasOwnProperty(t)&&((e=Object.create(e)).wrapped=!0),this.elementProperties.set(t,e),!e.noAccessor){let n=Symbol(),i=this.getPropertyDescriptor(t,n,e);i!==void 0&&je(this.prototype,t,i)}}static getPropertyDescriptor(t,e,n){let{get:i,set:r}=Ve(this.prototype,t)??{get(){return this[e]},set(s){this[e]=s}};return{get:i,set(s){let d=i?.call(this);r?.call(this,s),this.requestUpdate(t,d,n)},configurable:!0,enumerable:!0}}static getPropertyOptions(t){return this.elementProperties.get(t)??Vt}static _$Ei(){if(this.hasOwnProperty(z("elementProperties")))return;let t=Ke(this);t.finalize(),t.l!==void 0&&(this.l=[...t.l]),this.elementProperties=new Map(t.elementProperties)}static finalize(){if(this.hasOwnProperty(z("finalized")))return;if(this.finalized=!0,this._$Ei(),this.hasOwnProperty(z("properties"))){let e=this.properties,n=[...Be(e),...Fe(e)];for(let i of n)this.createProperty(i,e[i])}let t=this[Symbol.metadata];if(t!==null){let e=litPropertyMetadata.get(t);if(e!==void 0)for(let[n,i]of e)this.elementProperties.set(n,i)}this._$Eh=new Map;for(let[e,n]of this.elementProperties){let i=this._$Eu(e,n);i!==void 0&&this._$Eh.set(i,e)}this.elementStyles=this.finalizeStyles(this.styles)}static finalizeStyles(t){let e=[];if(Array.isArray(t)){let n=new Set(t.flat(1/0).reverse());for(let i of n)e.unshift(mt(i))}else t!==void 0&&e.push(mt(t));return e}static _$Eu(t,e){let n=e.attribute;return n===!1?void 0:typeof n=="string"?n:typeof t=="string"?t.toLowerCase():void 0}constructor(){super(),this._$Ep=void 0,this.isUpdatePending=!1,this.hasUpdated=!1,this._$Em=null,this._$Ev()}_$Ev(){this._$ES=new Promise(t=>this.enableUpdating=t),this._$AL=new Map,this._$E_(),this.requestUpdate(),this.constructor.l?.forEach(t=>t(this))}addController(t){(this._$EO??=new Set).add(t),this.renderRoot!==void 0&&this.isConnected&&t.hostConnected?.()}removeController(t){this._$EO?.delete(t)}_$E_(){let t=new Map,e=this.constructor.elementProperties;for(let n of e.keys())this.hasOwnProperty(n)&&(t.set(n,this[n]),delete this[n]);t.size>0&&(this._$Ep=t)}createRenderRoot(){let t=this.shadowRoot??this.attachShadow(this.constructor.shadowRootOptions);return zt(t,this.constructor.elementStyles),t}connectedCallback(){this.renderRoot??=this.createRenderRoot(),this.enableUpdating(!0),this._$EO?.forEach(t=>t.hostConnected?.())}enableUpdating(t){}disconnectedCallback(){this._$EO?.forEach(t=>t.hostDisconnected?.())}attributeChangedCallback(t,e,n){this._$AK(t,n)}_$ET(t,e){let n=this.constructor.elementProperties.get(t),i=this.constructor._$Eu(t,n);if(i!==void 0&&n.reflect===!0){let r=(n.converter?.toAttribute!==void 0?n.converter:_t).toAttribute(e,n.type);this._$Em=t,r==null?this.removeAttribute(i):this.setAttribute(i,r),this._$Em=null}}_$AK(t,e){let n=this.constructor,i=n._$Eh.get(t);if(i!==void 0&&this._$Em!==i){let r=n.getPropertyOptions(i),s=typeof r.converter=="function"?{fromAttribute:r.converter}:r.converter?.fromAttribute!==void 0?r.converter:_t;this._$Em=i;let d=s.fromAttribute(e,r.type);this[i]=d??this._$Ej?.get(i)??d,this._$Em=null}}requestUpdate(t,e,n,i=!1,r){if(t!==void 0){let s=this.constructor;if(i===!1&&(r=this[t]),n??=s.getPropertyOptions(t),!((n.hasChanged??Bt)(r,e)||n.useDefault&&n.reflect&&r===this._$Ej?.get(t)&&!this.hasAttribute(s._$Eu(t,n))))return;this.C(t,e,n)}this.isUpdatePending===!1&&(this._$ES=this._$EP())}C(t,e,{useDefault:n,reflect:i,wrapped:r},s){n&&!(this._$Ej??=new Map).has(t)&&(this._$Ej.set(t,s??e??this[t]),r!==!0||s!==void 0)||(this._$AL.has(t)||(this.hasUpdated||n||(e=void 0),this._$AL.set(t,e)),i===!0&&this._$Em!==t&&(this._$Eq??=new Set).add(t))}async _$EP(){this.isUpdatePending=!0;try{await this._$ES}catch(e){Promise.reject(e)}let t=this.scheduleUpdate();return t!=null&&await t,!this.isUpdatePending}scheduleUpdate(){return this.performUpdate()}performUpdate(){if(!this.isUpdatePending)return;if(!this.hasUpdated){if(this.renderRoot??=this.createRenderRoot(),this._$Ep){for(let[i,r]of this._$Ep)this[i]=r;this._$Ep=void 0}let n=this.constructor.elementProperties;if(n.size>0)for(let[i,r]of n){let{wrapped:s}=r,d=this[i];s!==!0||this._$AL.has(i)||d===void 0||this.C(i,void 0,r,d)}}let t=!1,e=this._$AL;try{t=this.shouldUpdate(e),t?(this.willUpdate(e),this._$EO?.forEach(n=>n.hostUpdate?.()),this.update(e)):this._$EM()}catch(n){throw t=!1,this._$EM(),n}t&&this._$AE(e)}willUpdate(t){}_$AE(t){this._$EO?.forEach(e=>e.hostUpdated?.()),this.hasUpdated||(this.hasUpdated=!0,this.firstUpdated(t)),this.updated(t)}_$EM(){this._$AL=new Map,this.isUpdatePending=!1}get updateComplete(){return this.getUpdateComplete()}getUpdateComplete(){return this._$ES}shouldUpdate(t){return!0}update(t){this._$Eq&&=this._$Eq.forEach(e=>this._$ET(e,this[e])),this._$EM()}updated(t){}firstUpdated(t){}};w.elementStyles=[],w.shadowRootOptions={mode:"open"},w[z("elementProperties")]=new Map,w[z("finalized")]=new Map,qe?.({ReactiveElement:w}),(tt.reactiveElementVersions??=[]).push("2.1.2");var xt=globalThis,Ft=o=>o,et=xt.trustedTypes,Kt=et?et.createPolicy("lit-html",{createHTML:o=>o}):void 0,Zt="$lit$",E=`lit$${Math.random().toFixed(9).slice(2)}$`,Jt="?"+E,Ge=`<${Jt}>`,T=document,V=()=>T.createComment(""),B=o=>o===null||typeof o!="object"&&typeof o!="function",At=Array.isArray,Ye=o=>At(o)||typeof o?.[Symbol.iterator]=="function",gt=`[ 	
\f\r]`,j=/<(?:(!--|\/[^a-zA-Z])|(\/?[a-zA-Z][^>\s]*)|(\/?$))/g,Wt=/-->/g,qt=/>/g,S=RegExp(`>|${gt}(?:([^\\s"'>=/]+)(${gt}*=${gt}*(?:[^ 	
\f\r"'\`<>=]|("|')|))|$)`,"g"),Gt=/'/g,Yt=/"/g,Qt=/^(?:script|style|textarea|title)$/i,Et=o=>(t,...e)=>({_$litType$:o,strings:t,values:e}),u=Et(1),Rn=Et(2),On=Et(3),x=Symbol.for("lit-noChange"),c=Symbol.for("lit-nothing"),Xt=new WeakMap,k=T.createTreeWalker(T,129);function te(o,t){if(!At(o)||!o.hasOwnProperty("raw"))throw Error("invalid template strings array");return Kt!==void 0?Kt.createHTML(t):t}var Xe=(o,t)=>{let e=o.length-1,n=[],i,r=t===2?"<svg>":t===3?"<math>":"",s=j;for(let d=0;d<e;d++){let a=o[d],h,f,p=-1,_=0;for(;_<a.length&&(s.lastIndex=_,f=s.exec(a),f!==null);)_=s.lastIndex,s===j?f[1]==="!--"?s=Wt:f[1]!==void 0?s=qt:f[2]!==void 0?(Qt.test(f[2])&&(i=RegExp("</"+f[2],"g")),s=S):f[3]!==void 0&&(s=S):s===S?f[0]===">"?(s=i??j,p=-1):f[1]===void 0?p=-2:(p=s.lastIndex-f[2].length,h=f[1],s=f[3]===void 0?S:f[3]==='"'?Yt:Gt):s===Yt||s===Gt?s=S:s===Wt||s===qt?s=j:(s=S,i=void 0);let g=s===S&&o[d+1].startsWith("/>")?" ":"";r+=s===j?a+Ge:p>=0?(n.push(h),a.slice(0,p)+Zt+a.slice(p)+E+g):a+E+(p===-2?d:g)}return[te(o,r+(o[e]||"<?>")+(t===2?"</svg>":t===3?"</math>":"")),n]},F=class o{constructor({strings:t,_$litType$:e},n){let i;this.parts=[];let r=0,s=0,d=t.length-1,a=this.parts,[h,f]=Xe(t,e);if(this.el=o.createElement(h,n),k.currentNode=this.el.content,e===2||e===3){let p=this.el.content.firstChild;p.replaceWith(...p.childNodes)}for(;(i=k.nextNode())!==null&&a.length<d;){if(i.nodeType===1){if(i.hasAttributes())for(let p of i.getAttributeNames())if(p.endsWith(Zt)){let _=f[s++],g=i.getAttribute(p).split(E),C=/([.?@])?(.*)/.exec(_);a.push({type:1,index:r,name:C[2],strings:g,ctor:C[1]==="."?bt:C[1]==="?"?vt:C[1]==="@"?$t:H}),i.removeAttribute(p)}else p.startsWith(E)&&(a.push({type:6,index:r}),i.removeAttribute(p));if(Qt.test(i.tagName)){let p=i.textContent.split(E),_=p.length-1;if(_>0){i.textContent=et?et.emptyScript:"";for(let g=0;g<_;g++)i.append(p[g],V()),k.nextNode(),a.push({type:2,index:++r});i.append(p[_],V())}}}else if(i.nodeType===8)if(i.data===Jt)a.push({type:2,index:r});else{let p=-1;for(;(p=i.data.indexOf(E,p+1))!==-1;)a.push({type:7,index:r}),p+=E.length-1}r++}}static createElement(t,e){let n=T.createElement("template");return n.innerHTML=t,n}};function P(o,t,e=o,n){if(t===x)return t;let i=n!==void 0?e._$Co?.[n]:e._$Cl,r=B(t)?void 0:t._$litDirective$;return i?.constructor!==r&&(i?._$AO?.(!1),r===void 0?i=void 0:(i=new r(o),i._$AT(o,e,n)),n!==void 0?(e._$Co??=[])[n]=i:e._$Cl=i),i!==void 0&&(t=P(o,i._$AS(o,t.values),i,n)),t}var yt=class{constructor(t,e){this._$AV=[],this._$AN=void 0,this._$AD=t,this._$AM=e}get parentNode(){return this._$AM.parentNode}get _$AU(){return this._$AM._$AU}u(t){let{el:{content:e},parts:n}=this._$AD,i=(t?.creationScope??T).importNode(e,!0);k.currentNode=i;let r=k.nextNode(),s=0,d=0,a=n[0];for(;a!==void 0;){if(s===a.index){let h;a.type===2?h=new K(r,r.nextSibling,this,t):a.type===1?h=new a.ctor(r,a.name,a.strings,this,t):a.type===6&&(h=new wt(r,this,t)),this._$AV.push(h),a=n[++d]}s!==a?.index&&(r=k.nextNode(),s++)}return k.currentNode=T,i}p(t){let e=0;for(let n of this._$AV)n!==void 0&&(n.strings!==void 0?(n._$AI(t,n,e),e+=n.strings.length-2):n._$AI(t[e])),e++}},K=class o{get _$AU(){return this._$AM?._$AU??this._$Cv}constructor(t,e,n,i){this.type=2,this._$AH=c,this._$AN=void 0,this._$AA=t,this._$AB=e,this._$AM=n,this.options=i,this._$Cv=i?.isConnected??!0}get parentNode(){let t=this._$AA.parentNode,e=this._$AM;return e!==void 0&&t?.nodeType===11&&(t=e.parentNode),t}get startNode(){return this._$AA}get endNode(){return this._$AB}_$AI(t,e=this){t=P(this,t,e),B(t)?t===c||t==null||t===""?(this._$AH!==c&&this._$AR(),this._$AH=c):t!==this._$AH&&t!==x&&this._(t):t._$litType$!==void 0?this.$(t):t.nodeType!==void 0?this.T(t):Ye(t)?this.k(t):this._(t)}O(t){return this._$AA.parentNode.insertBefore(t,this._$AB)}T(t){this._$AH!==t&&(this._$AR(),this._$AH=this.O(t))}_(t){this._$AH!==c&&B(this._$AH)?this._$AA.nextSibling.data=t:this.T(T.createTextNode(t)),this._$AH=t}$(t){let{values:e,_$litType$:n}=t,i=typeof n=="number"?this._$AC(t):(n.el===void 0&&(n.el=F.createElement(te(n.h,n.h[0]),this.options)),n);if(this._$AH?._$AD===i)this._$AH.p(e);else{let r=new yt(i,this),s=r.u(this.options);r.p(e),this.T(s),this._$AH=r}}_$AC(t){let e=Xt.get(t.strings);return e===void 0&&Xt.set(t.strings,e=new F(t)),e}k(t){At(this._$AH)||(this._$AH=[],this._$AR());let e=this._$AH,n,i=0;for(let r of t)i===e.length?e.push(n=new o(this.O(V()),this.O(V()),this,this.options)):n=e[i],n._$AI(r),i++;i<e.length&&(this._$AR(n&&n._$AB.nextSibling,i),e.length=i)}_$AR(t=this._$AA.nextSibling,e){for(this._$AP?.(!1,!0,e);t!==this._$AB;){let n=Ft(t).nextSibling;Ft(t).remove(),t=n}}setConnected(t){this._$AM===void 0&&(this._$Cv=t,this._$AP?.(t))}},H=class{get tagName(){return this.element.tagName}get _$AU(){return this._$AM._$AU}constructor(t,e,n,i,r){this.type=1,this._$AH=c,this._$AN=void 0,this.element=t,this.name=e,this._$AM=i,this.options=r,n.length>2||n[0]!==""||n[1]!==""?(this._$AH=Array(n.length-1).fill(new String),this.strings=n):this._$AH=c}_$AI(t,e=this,n,i){let r=this.strings,s=!1;if(r===void 0)t=P(this,t,e,0),s=!B(t)||t!==this._$AH&&t!==x,s&&(this._$AH=t);else{let d=t,a,h;for(t=r[0],a=0;a<r.length-1;a++)h=P(this,d[n+a],e,a),h===x&&(h=this._$AH[a]),s||=!B(h)||h!==this._$AH[a],h===c?t=c:t!==c&&(t+=(h??"")+r[a+1]),this._$AH[a]=h}s&&!i&&this.j(t)}j(t){t===c?this.element.removeAttribute(this.name):this.element.setAttribute(this.name,t??"")}},bt=class extends H{constructor(){super(...arguments),this.type=3}j(t){this.element[this.name]=t===c?void 0:t}},vt=class extends H{constructor(){super(...arguments),this.type=4}j(t){this.element.toggleAttribute(this.name,!!t&&t!==c)}},$t=class extends H{constructor(t,e,n,i,r){super(t,e,n,i,r),this.type=5}_$AI(t,e=this){if((t=P(this,t,e,0)??c)===x)return;let n=this._$AH,i=t===c&&n!==c||t.capture!==n.capture||t.once!==n.once||t.passive!==n.passive,r=t!==c&&(n===c||i);i&&this.element.removeEventListener(this.name,this,n),r&&this.element.addEventListener(this.name,this,t),this._$AH=t}handleEvent(t){typeof this._$AH=="function"?this._$AH.call(this.options?.host??this.element,t):this._$AH.handleEvent(t)}},wt=class{constructor(t,e,n){this.element=t,this.type=6,this._$AN=void 0,this._$AM=e,this.options=n}get _$AU(){return this._$AM._$AU}_$AI(t){P(this,t)}};var Ze=xt.litHtmlPolyfillSupport;Ze?.(F,K),(xt.litHtmlVersions??=[]).push("3.3.3");var ee=(o,t,e)=>{let n=e?.renderBefore??t,i=n._$litPart$;if(i===void 0){let r=e?.renderBefore??null;n._$litPart$=i=new K(t.insertBefore(V(),r),r,void 0,e??{})}return i._$AI(o),i};var Ct=globalThis,b=class extends w{constructor(){super(...arguments),this.renderOptions={host:this},this._$Do=void 0}createRenderRoot(){let t=super.createRenderRoot();return this.renderOptions.renderBefore??=t.firstChild,t}update(t){let e=this.render();this.hasUpdated||(this.renderOptions.isConnected=this.isConnected),super.update(t),this._$Do=ee(e,this.renderRoot,this.renderOptions)}connectedCallback(){super.connectedCallback(),this._$Do?.setConnected(!0)}disconnectedCallback(){super.disconnectedCallback(),this._$Do?.setConnected(!1)}render(){return x}};b._$litElement$=!0,b.finalized=!0,Ct.litElementHydrateSupport?.({LitElement:b});var Je=Ct.litElementPolyfillSupport;Je?.({LitElement:b});(Ct.litElementVersions??=[]).push("4.2.2");async function R(o,t,e,n,i){try{await o.callService(t,e,n,{entity_id:i})}catch{}}function ne(o,t,e){return R(o,"number","set_value",{value:e},t)}function W(o,t,e){return R(o,"timerify","add_time",{minutes:e},t)}function St(o,t){return R(o,"timerify","run",{},t)}function O(o,t){return R(o,"timerify","stop",{},t)}function oe(o,t,e){return R(o,"switch",e?"turn_on":"turn_off",{},t)}function ie(o,t,e){return R(o,"timerify","cancel_command",{command_id:e},t)}var re={card_entity_not_found:"Entity not found: {entity}",card_not_a_timer:"{entity} is not the Run for number of a Timerify timer",card_timer_incomplete:"The timer of {entity} cannot be shown: its target or one of its sensors is missing. Open the timer's page to see why.",card_not_allowed:"You are not allowed to see the timer {entity}",card_ends_at_disabled:"The Ends at sensor of this timer, {sensor}, is disabled. Enable it for the card to work",card_error_entity:"Choose the Run for number of a timer",card_error_layout:"The layout is pill or round",card_error_presets:"Presets are whole minutes from 1 to 1440",card_error_chip:"The quick chip is whole minutes from 1 to 1440",card_error_press:"Tap, double tap and hold can each be popup, run, stop, run_or_stop, action or none",card_error_action:"A Home Assistant action is a set of settings, such as action: more-info",card_error_show_turn_off:"show_turn_off is true or false",card_close:"Close",card_until:"until {time}",card_add_time:"Add {duration}",card_subtract_time:"Take off {duration}",card_stop:"Stop",card_turn_off:"Turn off",card_schedule:"Schedule",card_commands:"Pending commands",card_commands_disabled:"Pending commands are hidden: the Next command sensor, {sensor}, is disabled",card_command_on:"On at {time}",card_command_on_for:"On at {time} for {duration}",card_command_off:"Off at {time}",card_cancel_command:"Cancel",card_settings:"Settings",card_picker_description:"The countdown, presets and schedule of a Timerify timer",card_editor_entity:"Timer",card_editor_layout:"Layout",card_editor_layout_pill:"Pill",card_editor_layout_round:"Round",card_editor_name:"Name",card_editor_icon:"Icon",card_editor_presets:"Duration presets (minutes)",card_editor_presets_helper:"Leave empty for {presets}",card_editor_chip:"Quick add chip (minutes, pill only)",card_editor_show_turn_off:"Show a Turn off button",card_editor_interactions:"Interactions",card_editor_tap:"Tap behavior",card_editor_double_tap:"Double tap behavior",card_editor_hold:"Hold behavior",card_editor_tap_action:"Tap action",card_editor_double_tap_action:"Double tap action",card_editor_hold_action:"Hold action",card_editor_press_popup:"Open the pop-up",card_editor_press_run:"Run for the default duration",card_editor_press_stop:"Stop",card_editor_press_run_or_stop:"Start or stop",card_editor_press_action:"Home Assistant action",card_editor_press_none:"Nothing",card_editor_action_helper:'Used when the behavior above is set to "Home Assistant action"'};var ae="common",de="timerify",Qe=`component.${de}.${ae}.`;function kt(o){return Qe+o}function tn(o,t){return o.replace(/\{(\w+)\}/g,(e,n)=>String(t?.[n]??e))}function l(o,t,e){return o?.localize(kt(t),e)||tn(re[t],e)}var q,se=Promise.resolve(),ce,le=new Set;function nt(o){return o.language!==q&&(q=o.language,se=en(o,o.language)),se}async function en(o,t){let e;try{e=await o.loadBackendTranslation(ae,de)}catch{q===t&&(q=void 0);return}q===t&&(ce={...o,localize:e},le.forEach(n=>n()))}function A(){return ce}function ue(o){le.add(o)}var G=[15,30,45,60,120],Pt=1440,Ht=["popup","run","stop","run_or_stop","action","none"],nn=["tap","double_tap","hold"],Rt=["tap_action","double_tap_action","hold_action"],m=class extends Error{constructor(e){super(l(A(),e));this.key=e}key};function he(o){let t=typeof o=="number"?o:typeof o=="string"&&/^\d+$/.test(o)?Number(o):void 0;return t!==void 0&&Number.isInteger(t)&&t>=1&&t<=Pt?t:void 0}function on(o){if(o===void 0||Array.isArray(o)&&o.length===0)return[...G];if(!Array.isArray(o))throw new m("card_error_presets");let t=new Set;for(let e of o){let n=he(e);if(n===void 0)throw new m("card_error_presets");t.add(n)}return[...t]}function rn(o){if(o===void 0)return;let t=he(o);if(t===void 0)throw new m("card_error_chip");return t}var fe=o=>typeof o=="object"&&o!==null?o:{},sn=o=>Ht.some(t=>t===o);function Tt(o,t){if(o===void 0)return t;if(!sn(o))throw new m("card_error_press");return o}function an(o){if(o===void 0)return!1;if(typeof o!="boolean")throw new m("card_error_show_turn_off");return o}var dn=o=>typeof o=="object"&&o!==null&&!Array.isArray(o);function me(o){let t={};for(let e of Rt){let n=o[e];if(n!==void 0){if(!dn(n))throw new m("card_error_action");t[e]=n}}return t}var pe=o=>typeof o=="number"||typeof o=="string";function _e(o){let t=fe(o),{entity:e,layout:n,presets:i,chip:r}=t;if(e!==void 0&&typeof e!="string")throw new m("card_error_entity");if(n!==void 0&&typeof n!="string")throw new m("card_error_layout");if(i!==void 0&&!(Array.isArray(i)&&i.every(pe)))throw new m("card_error_presets");if(r!==void 0&&!pe(r))throw new m("card_error_chip");if(t.show_turn_off!==void 0&&typeof t.show_turn_off!="boolean")throw new m("card_error_show_turn_off");for(let s of nn)if(t[s]!==void 0&&typeof t[s]!="string")throw new m("card_error_press");me(t)}function ge(o){let t=fe(o),{entity:e,layout:n="pill",name:i,icon:r}=t;if(typeof e!="string"||!/^number\.[a-z0-9_]+$/.test(e))throw new m("card_error_entity");if(n!=="pill"&&n!=="round")throw new m("card_error_layout");let s=rn(t.chip);return{entity:e,layout:n,...typeof i=="string"&&i!==""&&{name:i},...typeof r=="string"&&r!==""&&{icon:r},presets:on(t.presets),...s!==void 0&&{chip:s},show_turn_off:an(t.show_turn_off),tap:Tt(t.tap,"popup"),double_tap:Tt(t.double_tap,"none"),hold:Tt(t.hold,n==="round"?"run_or_stop":"none"),...me(t)}}var ot=class{#t;#e;#n;#o=!1;#i;constructor(t,e,n){this.#t=t,this.#e=e,this.#n=n,t.addController(this)}hostConnected(){this.#o=!0,this.#r()}hostUpdated(){this.#r()}hostDisconnected(){this.#o=!1,this.#r()}#r(){let t=this.#e(),e=this.#o&&t!==void 0&&t.getTime()>this.#n();e&&this.#i===void 0?this.#i=setInterval(()=>this.#t.requestUpdate(),1e3):!e&&this.#i!==void 0&&(clearInterval(this.#i),this.#i=void 0)}};var ye=o=>String(o).padStart(2,"0");function M(o){let t=Math.ceil(Math.max(0,o)),e=Math.floor(t/3600),n=Math.floor(t%3600/60),i=ye(t%60);return e>0?`${e}:${ye(n)}:${i}`:`${n}:${i}`}function cn({language:o,time_format:t}){if(t==="12"||t==="24")return t==="12";let e=new Intl.DateTimeFormat(t==="language"?o:void 0,{hour:"numeric"}).resolvedOptions();return e.hourCycle==="h11"||e.hourCycle==="h12"}var ln=864e5;function be(o,t){let e=new Intl.DateTimeFormat("en-US",{timeZone:o,year:"numeric",month:"numeric",day:"numeric"}).formatToParts(t),n=i=>Number(e.find(r=>r.type===i)?.value);return Date.UTC(n("year"),n("month")-1,n("day"))/ln}function Y(o,t,e){let{locale:n}=o,i=n.time_zone==="server"?o.config.time_zone:void 0,r=be(i,t.getTime())-be(i,e),s=r===0?{}:r>=1&&r<=6?{weekday:"short"}:{month:"short",day:"numeric"};return new Intl.DateTimeFormat(n.language,{...s,hour:"numeric",minute:"2-digit",hourCycle:cn(n)?"h12":"h23",timeZone:i}).format(t)}function v(o,t){let e=(s,d)=>new Intl.NumberFormat(o.locale.language,{style:"unit",unit:d,unitDisplay:"short",useGrouping:!1}).format(s),n=Math.floor(t/60),i=t%60,r=n>0?[e(n,"hour")]:[];return(i>0||n===0)&&r.push(e(i,"minute")),r.join(" ")}function ve(o,t,e,n,i){return e.includes(n)&&typeof i=="number"?new Intl.NumberFormat(o.locale.language,{style:"percent",maximumFractionDigits:1}).format(i/100):t===void 0?String(i):n==="hvac_mode"?o.formatEntityState(t,String(i)):o.formatEntityAttributeValue(t,n,i)}var $e={entity:"card_editor_entity",layout:"card_editor_layout",name:"card_editor_name",icon:"card_editor_icon",presets:"card_editor_presets",chip:"card_editor_chip",show_turn_off:"card_editor_show_turn_off",interactions:"card_editor_interactions",tap:"card_editor_tap",double_tap:"card_editor_double_tap",hold:"card_editor_hold",tap_action:"card_editor_tap_action",double_tap_action:"card_editor_double_tap_action",hold_action:"card_editor_hold_action"},un={popup:"card_editor_press_popup",run:"card_editor_press_run",stop:"card_editor_press_stop",run_or_stop:"card_editor_press_run_or_stop",action:"card_editor_press_action",none:"card_editor_press_none"},pn=o=>Object.hasOwn($e,o),hn=o=>o.endsWith("_action"),fn={locale:{language:"en"}};function we(){return A()??fn}function mn(){let o=we();return new Intl.ListFormat(o.locale.language,{style:"long",type:"conjunction"}).format(G.map(t=>v(o,t)))}async function xe(){let o=A(),t=Ht.map(e=>({value:e,label:l(o,un[e])}));return{schema:[{name:"entity",required:!0,selector:{entity:{filter:{integration:"timerify",domain:"number"}}}},{name:"layout",selector:{select:{options:[{value:"pill",label:l(o,"card_editor_layout_pill")},{value:"round",label:l(o,"card_editor_layout_round")}]}}},{name:"",type:"grid",schema:[{name:"name",selector:{text:{}}},{name:"icon",selector:{icon:{}}}]},{name:"presets",selector:{select:{multiple:!0,custom_value:!0,options:G.map(e=>({value:String(e),label:v(we(),e)}))}}},{name:"chip",selector:{number:{min:1,max:Pt,mode:"box"}}},{name:"show_turn_off",selector:{boolean:{}}},{name:"interactions",type:"expandable",flatten:!0,icon:"mdi:gesture-tap",schema:[{name:"tap",selector:{select:{options:t}}},{name:"tap_action",selector:{ui_action:{default_action:"more-info"}}},{name:"double_tap",selector:{select:{options:t}}},{name:"double_tap_action",selector:{ui_action:{default_action:"more-info"}}},{name:"hold",selector:{select:{options:t}}},{name:"hold_action",selector:{ui_action:{default_action:"more-info"}}}]}],assertConfig:_e,computeLabel:({name:e},n)=>pn(e)?n(kt($e[e])):"",computeHelper:({name:e})=>e==="presets"?l(A(),"card_editor_presets_helper",{presets:mn()}):hn(e)?l(A(),"card_editor_action_helper"):void 0}}function Ae(o,t,e){nt(o);let n=r=>{let s=o.entities[r];return s?.platform==="timerify"&&s.translation_key==="run_for"},i=r=>r.filter(n).sort()[0];return{entity:i(t)??i(e)??i(Object.keys(o.entities))??"",layout:"pill",presets:G.map(String)}}var _n="not_found",gn="timer_incomplete",yn="unauthorized";async function Ce(o,t){let e=Date.now();try{let n=await o.callWS({type:"timerify/timer",entity_id:t}),i=Ot(n.server_time),r=i===void 0?0:i-(e+Date.now())/2;return{status:"found",info:n,clockOffset:r}}catch(n){let i=typeof n=="object"&&n!==null&&"code"in n?n.code:"";return i===_n?{status:"not_found"}:i===gn?{status:"incomplete"}:{status:i===yn?"unauthorized":"failed"}}}var X=o=>Date.now()+(o.status==="found"?o.clockOffset:0),it=(o,t)=>o.disabled_sensors.includes(t),L=o=>o!==void 0&&o.state!=="unavailable"&&o.state!=="unknown";function bn(o,t){return o===void 0||o.state==="unavailable"||o.state==="unknown"?!1:t.states.includes(o.state)===(t.match==="is")}var vn="mdi:timer-outline",Ee=o=>o===void 0||o.state==="unavailable";function Ot(o){let t=typeof o=="string"?Date.parse(o):Number.NaN;return Number.isNaN(t)?void 0:t}function Se(o,t,e,n){let i=e.status==="found"?e.info:void 0,r=o.states[t.entity],s=i&&o.states[i.target],d=t.name||s&&o.formatEntityName(s,void 0)||r?.attributes.friendly_name||t.entity,a=t.icon?{icon:t.icon}:s?{stateObj:s}:{icon:vn},h={name:d,icon:a,target:s,remaining:0},f=i&&o.states[i.ends_at];if(i===void 0||f===void 0||Ee(r)||Ee(f))return{...h,state:"unavailable",progress:0};let p=Ot(f.state);if(p===void 0)return bn(s,i.target_on)?{...h,state:"open",progress:1}:{...h,state:"idle",progress:0};let _=Ot(f.attributes.started_at),g=_===void 0?0:(p-_)/1e3,C=Math.max(0,(p-n)/1e3);return{...h,state:"counting",remaining:C,progress:g>0?Math.min(1,C/g):1,endsAt:new Date(p)}}var N=({state:o})=>o==="counting"||o==="open";function rt(o,t){return t?[o,t.ends_at,t.next_command,t.target,...t.intervals.map(({entity_id:e})=>e)]:[o]}var $n=["locale","language","localize","config","user","connected","entities","formatEntityName","formatEntityState","formatEntityAttributeValue"];function st(o,t,e){for(let i of o.keys())if(i!=="hass")return!0;let n=o.get("hass");return n===void 0||t===void 0?!0:$n.some(i=>n[i]!==t[i])||e.some(i=>n.states[i]!==t.states[i])}function at(o){return"stateObj"in o.icon?u`<ha-state-icon .stateObj=${o.icon.stateObj}></ha-state-icon>`:u`<ha-icon .icon=${o.icon.icon}></ha-icon>`}var dt=o=>o.tap==="popup"?"dialog":void 0,U=o=>o.tap!=="none"||o.double_tap!=="none"||o.hold!=="none";function ct(o,t,e,n){return!t.show_turn_off||!N(o)?c:u`
    <button class="turn-off" type="button" @click=${n}>${l(e,"card_turn_off")}</button>
  `}function wn(o,t,e){if(o.state!=="unavailable")return o.target?e.formatEntityState(o.target):"";let n=e.states[t.entity];if(L(n))return"";let i={entity_id:t.entity,state:"unavailable",attributes:{}};return e.formatEntityState(n??i,"unavailable")}function lt(o,t,e,n){if(o.state!=="counting"||o.endsAt===void 0)return wn(o,t,e);let i=Y(e,o.endsAt,n);return u`
    <span class="remaining">${M(o.remaining)}</span>
    <span class="until">${l(e,"card_until",{time:i})}</span>
  `}var ke=y`
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
  /* The small buttons that sit on the card beside its body: the pill's chip, and Turn off. */
  .chip,
  .turn-off {
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
  .chip:focus-visible,
  .turn-off:focus-visible {
    outline: 2px solid var(--primary-color);
    outline-offset: 2px;
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
`;var $=o=>o??c;var Te={ATTRIBUTE:1,CHILD:2,PROPERTY:3,BOOLEAN_ATTRIBUTE:4,EVENT:5,ELEMENT:6},Pe=o=>(...t)=>({_$litDirective$:o,values:t}),ut=class{constructor(t){}get _$AU(){return this._$AM._$AU}_$AT(t,e,n){this._$Ct=t,this._$AM=e,this._$Ci=n}_$AS(t,e){return this.update(t,e)}update(t,e){return this.render(...e)}};var He="important",xn=" !"+He,Re=Pe(class extends ut{constructor(o){if(super(o),o.type!==Te.ATTRIBUTE||o.name!=="style"||o.strings?.length>2)throw Error("The `styleMap` directive must be used in the `style` attribute and must be the only part in the attribute.")}render(o){return Object.keys(o).reduce((t,e)=>{let n=o[e];return n==null?t:t+`${e=e.includes("-")?e:e.replace(/(?:^(webkit|moz|ms|o)|)(?=[A-Z])/g,"-$&").toLowerCase()}:${n};`},"")}update(o,[t]){let{style:e}=o.element;if(this.ft===void 0)return this.ft=new Set(Object.keys(t)),this.render(t);for(let n of this.ft)t[n]==null&&(this.ft.delete(n),n.includes("-")?e.removeProperty(n):e[n]=null);for(let n in t){let i=t[n];if(i!=null){this.ft.add(n);let r=typeof i=="string"&&i.endsWith(xn);n.includes("-")||r?e.setProperty(n,r?i.slice(0,-11):i,r?He:""):e[n]=i}}return x}});function Oe(o,t,e,n,i,r,s){let d=Math.round(o.progress*1e3)/10,a=U(t);return u`
    <ha-card class="pill ${o.state}">
      <div
        class="body"
        role=${$(a?"button":void 0)}
        tabindex=${$(a?"0":void 0)}
        aria-haspopup=${$(dt(t))}
        aria-labelledby=${$(a?"label":void 0)}
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
          <span class="fill" style=${Re({width:`${d}%`})}></span>
        </span>
      </div>
      <div class="content">
        <span class="icon">${at(o)}</span>
        <span class="text" id="label">
          <span class="name">${o.name}</span>
          <span class="status">${lt(o,t,e,s)}</span>
        </span>
        ${ct(o,t,e,r)}
        ${t.chip===void 0?c:u`
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
  `}var Me=y`
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
  .chip:disabled {
    color: var(--disabled-text-color);
    cursor: default;
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
`;function An(o,t){let e=t?.attributes.max;return typeof e=="number"&&Number.isFinite(e)?o.filter(n=>n<=e):[...o]}function En(o){let t=o?.attributes.commands;return Array.isArray(t)?t.flatMap(e=>{if(typeof e!="object"||e===null)return[];let{id:n,at:i,action:r,minutes:s,settings:d}=e,a=typeof i=="string"?new Date(i):void 0;return typeof n!="string"||a===void 0||Number.isNaN(a.getTime())||r!=="on"&&r!=="off"?[]:[{id:n,at:a,action:r,minutes:typeof s=="number"&&s>0?s:null,settings:typeof d=="object"&&d!==null?Object.entries(d):[]}]}):[]}var Cn=o=>`/config/integrations/integration/timerify#config_entry=${encodeURIComponent(o)}`,pt=class extends b{static properties={hass:{attribute:!1},config:{attribute:!1},lookup:{attribute:!1},view:{attribute:!1},opened:{state:!0}};static styles=y`
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
  `;constructor(){super(),this.opened=!1}open(){this.opened=!0}close(){this.#t?.close(),this.#s()}disconnectedCallback(){super.disconnectedCallback(),this.close()}get#t(){return this.renderRoot.querySelector("dialog")}#e=()=>{this.#t?.open||this.#s()};#n=!1;#o=t=>{this.#n=t.target===t.currentTarget};#i=t=>{this.#n&&=t.target===t.currentTarget};#r=()=>{this.#n=!1};#d=t=>{let e=this.#n&&t.target===t.currentTarget;this.#n=!1,e&&this.close()};#s(){this.opened&&(this.opened=!1,this.dispatchEvent(new CustomEvent("closed")))}shouldUpdate(t){if(!this.hasUpdated||t.has("opened"))return!0;let e=rt(this.config.entity,this.lookup.info);return this.opened&&st(t,this.hass,e)}updated(t){let e=this.#t;t.has("opened")&&this.opened&&e&&!e.open&&e.showModal()}render(){return u`
      <dialog
        aria-labelledby="title"
        @cancel=${()=>this.close()}
        @close=${this.#e}
        @pointerdown=${this.#o}
        @pointerup=${this.#i}
        @pointercancel=${this.#r}
        @click=${this.#d}
      >
        ${this.opened?this.#a():c}
      </dialog>
    `}#a(){let{hass:t,view:e}=this,n=X(this.lookup);return u`
      <div class="wrapper">
        <header>
          <h2 id="title">${e.name}</h2>
          <button class="close" @click=${()=>this.close()}>${l(t,"card_close")}</button>
        </header>
        ${this.#u(n)} ${this.#p()} ${this.#h()} ${this.#c(n)}
        ${this.#m()}
      </div>
    `}#u(t){let{hass:e,view:n}=this;if(n.state!=="counting"||n.endsAt===void 0)return c;let i=Y(e,n.endsAt,t);return u`
      <p class="countdown">
        <span class="remaining">${M(n.remaining)}</span>
        <span class="until">${l(e,"card_until",{time:i})}</span>
      </p>
    `}#p(){let{hass:t,config:e,view:n}=this,i=v(t,5),r=n.state==="counting",s=N(n),d=n.state==="unavailable",a=An(e.presets,t.states[e.entity]);return u`
      ${a.length===0?c:u`
            <div class="presets">
              ${a.map(h=>u`
                  <button
                    class="action preset"
                    ?disabled=${d}
                    @click=${()=>{ne(t,e.entity,h)}}
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
          ?disabled=${!r}
          @click=${()=>{W(t,e.entity,-5)}}
        >
          −${i}
        </button>
        <button
          class="action step"
          aria-label=${l(t,"card_add_time",{duration:i})}
          ?disabled=${d}
          @click=${()=>{W(t,e.entity,5)}}
        >
          +${i}
        </button>
        <button
          class="action stop"
          ?disabled=${!s}
          @click=${()=>{O(t,e.entity)}}
        >
          ${l(t,"card_stop")}
        </button>
      </div>
    `}#h(){let{intervals:t}=this.lookup.info;return t.length===0?c:u`
      <section class="schedule">
        <h3>${l(this.hass,"card_schedule")}</h3>
        <ul>
          ${t.map(e=>u`<li>${this.#l(e)}</li>`)}
        </ul>
      </section>
    `}#l({entity_id:t,title:e}){let{hass:n}=this,i=n.states[t],r=i!==void 0&&i.state!=="unavailable",s=r&&i.state==="on",d=i??{entity_id:t,state:"unavailable",attributes:{}};return u`
      <button
        class="interval"
        role="switch"
        aria-checked=${s?"true":"false"}
        ?disabled=${!r}
        @click=${()=>{oe(n,t,!s)}}
      >
        <span class="label">
          <span class="title">${e}</span>
          ${r?c:u`<span class="state">${n.formatEntityState(d,"unavailable")}</span>`}
        </span>
        <span class="track" aria-hidden="true"><span class="knob"></span></span>
      </button>
    `}#c(t){let{hass:e,config:n,view:i}=this,{info:r}=this.lookup;if(it(r,r.next_command))return u`
        <section class="commands">
          <p class="note">${l(e,"card_commands_disabled",{sensor:r.next_command})}</p>
        </section>
      `;let s=En(e.states[r.next_command]);if(s.length===0)return c;let d=i.state==="unavailable";return u`
      <section class="commands">
        <h3>${l(e,"card_commands")}</h3>
        <ul>
          ${s.map((a,h)=>{let f=a.settings.map(([p,_])=>ve(e,i.target,r.percent_settings,p,_));return u`
              <li>
                <div class="command" id="command-${h}">
                  <span class="what">${this.#f(a,t)}</span>
                  ${f.length===0?c:u`<span class="settings">${f.join(", ")}</span>`}
                </div>
                <button
                  class="cancel"
                  aria-label=${l(e,"card_cancel_command")}
                  aria-describedby="command-${h}"
                  ?disabled=${d}
                  @click=${()=>{ie(e,n.entity,a.id)}}
                >
                  <span aria-hidden="true">×</span>
                </button>
              </li>
            `})}
        </ul>
      </section>
    `}#f(t,e){let{hass:n}=this,i=Y(n,t.at,e);return t.action==="off"?l(n,"card_command_off",{time:i}):t.minutes===null?l(n,"card_command_on",{time:i}):l(n,"card_command_on_for",{time:i,duration:v(n,t.minutes)})}#m(){return this.hass.user?.is_admin?u`
      <footer>
        <a href=${Cn(this.lookup.info.entry_id)} @click=${this.#_}>
          ${l(this.hass,"card_settings")}
        </a>
      </footer>
    `:c}#_=t=>{!t.ctrlKey&&!t.metaKey&&!t.shiftKey&&this.close()}};var Le="data-held",ht=class{#t;#e;#n=!1;#o;#i;#r=!1;#d=!1;#s;#a=t=>this.#l(t);constructor(t,e){this.#t=t,this.#e=e,t.addController(this)}hostDisconnected(){this.#n=!1,this.#d=!1,this.#p(),this.#c()}cancelPress(){this.#c()}binding(){return{click:t=>{if(this.#d){this.#d=!1,t.preventDefault(),t.stopPropagation();return}this.#u()},keydown:t=>{t.key==="Enter"?(t.preventDefault(),t.repeat||this.#e().tap()):t.key===" "&&(t.preventDefault(),this.#n=!0)},keyup:t=>{if(t.key!==" ")return;let e=this.#n;this.#n=!1,e&&this.#e().tap()},pointerdown:t=>this.#h(t),pointerup:t=>{if(t.pointerId!==this.#o)return;let e=this.#r;this.#c();let{hold:n}=this.#e();e&&n!==void 0&&(this.#d=!0,n())},pointercancel:t=>this.#l(t),pointerleave:t=>this.#l(t),contextmenu:t=>{this.#o!==void 0&&t.preventDefault()}}}#u(){let{tap:t,doubleTap:e}=this.#e(),n=this.#s!==void 0;this.#p(),e===void 0?t():n?e():this.#s=setTimeout(()=>{this.#s=void 0,this.#e().tap()},250)}#p(){clearTimeout(this.#s),this.#s=void 0}#h(t){this.#e().hold===void 0||!t.isPrimary||t.button!==0||(this.#d=!1,this.#c(),this.#o=t.pointerId,window.addEventListener("pointerup",this.#a),window.addEventListener("pointercancel",this.#a),this.#i=setTimeout(()=>{this.#i=void 0,this.#r=!0,this.#t.setAttribute(Le,"")},500))}#l(t){t.pointerId===this.#o&&this.#c()}#c(){clearTimeout(this.#i),this.#i=void 0,this.#o=void 0,this.#r=!1,window.removeEventListener("pointerup",this.#a),window.removeEventListener("pointercancel",this.#a),this.#t.removeAttribute(Le)}};var D=80,Ue=6,Lt=(D-Ue)/2,Ne=2*Math.PI*Lt;function Sn(o){if(o.state!=="counting")return u`<span class="icon">${at(o)}</span>`;let t=M(o.remaining);return u`<span class="time" aria-hidden="true">${t}</span>`}function De(o,t,e,n,i,r){let s=D/2,d=U(t);return u`
    <ha-card class="round ${o.state} ${t.show_turn_off?"with-turn-off":""}">
      <div
        class="body"
        role=${$(d?"button":void 0)}
        tabindex=${$(d?"0":void 0)}
        aria-haspopup=${$(dt(t))}
        aria-labelledby=${$(d?"label":void 0)}
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
          <svg class="ring" viewBox="0 0 ${D} ${D}" aria-hidden="true">
            <circle class="track" cx=${s} cy=${s} r=${Lt}></circle>
            <circle
              class="progress"
              cx=${s}
              cy=${s}
              r=${Lt}
              transform="rotate(-90 ${s} ${s})"
              stroke-dasharray=${Ne}
              stroke-dashoffset=${(1-o.progress)*Ne}
            ></circle>
          </svg>
          <span class="centre">
            ${Sn(o)}
          </span>
        </div>
        <span class="text" id="label">
          <span class="name">${o.name}</span>
          <span class="status">${lt(o,t,e,r)}</span>
        </span>
        ${t.show_turn_off?u`<div class="turn-off-slot">${ct(o,t,e,i)}</div>`:c}
      </div>
    </ha-card>
  `}var Ie=y`
  ha-card.round {
    --timerify-radius: var(--ha-card-border-radius, var(--ha-border-radius-lg, 12px));
    height: 120px;
  }
  /* A row taller than the tile, for the Turn off button: three rows of the sections grid. */
  ha-card.round.with-turn-off {
    height: 184px;
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
    width: ${D}px;
    height: ${D}px;
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
    stroke-width: ${Ue};
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
  .turn-off-slot {
    display: flex;
    flex: none;
    align-items: center;
    justify-content: center;
    height: 32px;
    margin-top: 4px;
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
`;var Nt="timerify-card",Z={pill:{columns:6,rows:1,min_columns:3,min_rows:1,max_rows:1},round:{columns:3,rows:2,min_columns:2,min_rows:2,max_rows:3},pillWithTurnOff:{columns:8,rows:1,min_columns:8,min_rows:1,max_rows:1},pillWithTurnOffAndChip:{columns:11,rows:1,min_columns:11,min_rows:1,max_rows:1},roundWithTurnOff:{columns:5,rows:3,min_columns:5,min_rows:3,max_rows:3}},Ut=class extends b{static properties={hass:{attribute:!1,noAccessor:!0},_config:{state:!0},_lookup:{state:!0}};static styles=[ke,Me,Ie,y`
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
    `];static getConfigForm=xe;static getStubConfig=Ae;#t;#e=new Set;#n=!1;#o=!1;#i=new ht(this,()=>this.#_());#r=this.#i.binding();#d=()=>{let{_config:t,hass:e}=this;t?.chip!==void 0&&e!==void 0&&W(e,t.entity,t.chip)};#s=()=>{let{_config:t,hass:e}=this;t!==void 0&&e!==void 0&&O(e,t.entity)};#a;#u=!1;constructor(){super(),this._lookup={status:"pending"},new ot(this,()=>this.#a?.endsAt,()=>X(this._lookup))}get hass(){return this.#t}set hass(t){let e=this.#t;this.#t=t,this.requestUpdate("hass",e),this.#p(e,t)}setConfig(t){let e=ge(t),n=this._config?.entity!==e.entity;this._config=e,n&&(this._lookup={status:"pending"},this.#l())}getCardSize(){return this._config?.layout!=="round"?1:this._config.show_turn_off?4:3}getGridOptions(){let t=this._config;return t?.layout==="round"?t.show_turn_off?Z.roundWithTurnOff:Z.round:t?.show_turn_off?t.chip===void 0?Z.pillWithTurnOff:Z.pillWithTurnOffAndChip:Z.pill}async getUpdateComplete(){let t=await super.getUpdateComplete();for(;this.#e.size>0;)await Promise.allSettled([...this.#e]),t=await super.getUpdateComplete();return t}#p(t,e){let n=t!==void 0&&e.connected&&!t.connected;(t===void 0||t.language!==e.language||n)&&this.#h(nt(e));let i=this._config?.entity;i!==void 0&&(t===void 0||t.entities!==e.entities||n||L(e.states[i])&&!L(t.states[i]))&&this.#l()}#h(t){let e=t.finally(()=>this.#e.delete(e));this.#e.add(e)}#l(){if(this.#n){this.#o=!0;return}this.#n=!0,this.#h(this.#c())}async#c(){try{do{this.#o=!1;let t=this._config?.entity;if(this.#t===void 0||t===void 0)return;let e=await Ce(this.#t,t);this.#o||(this._lookup=e)}while(this.#o)}finally{this.#n=!1}}willUpdate(){this.#u=this.shadowRoot?.activeElement?.classList.contains("turn-off")===!0}updated(){this.#u&&this.shadowRoot?.querySelector(".turn-off")===null&&this.#f()}#f(){let t=this._config;t!==void 0&&U(t)&&this.renderRoot.querySelector(".body")?.focus()}shouldUpdate(t){let e=this._lookup.status==="found"?this._lookup.info:void 0,n=this._config?rt(this._config.entity,e):[];return st(t,this.#t,n)}get#m(){return this.renderRoot.querySelector("timerify-card-popup")}#_(){let t=this._config,e={tap:()=>this.#g("tap")};return t!==void 0&&t.double_tap!=="none"&&(e.doubleTap=()=>this.#g("double_tap")),t!==void 0&&t.hold!=="none"&&(e.hold=()=>this.#g("hold")),e}#g(t){let{_config:e,hass:n}=this;if(!(e===void 0||n===void 0))switch(e[t]){case"popup":this.#i.cancelPress(),this.#m?.open();break;case"run":St(n,e.entity);break;case"stop":O(n,e.entity);break;case"run_or_stop":this.#y(n,e);break;case"action":this.#b(t,e);break;case"none":break}}#y(t,e){let n=this.#a;n!==void 0&&(N(n)?O(t,e.entity):n.state==="idle"&&St(t,e.entity))}#b(t,e){if(this._lookup.status!=="found")return;let n=Object.fromEntries(Rt.filter(i=>e[i]!==void 0).map(i=>[i,e[i]]));this.dispatchEvent(new CustomEvent("hass-action",{detail:{config:{entity:this._lookup.info.target,...n},action:t},bubbles:!0,composed:!0}))}#v(t,e){let n=this._lookup;if(n.status==="unauthorized")return l(t,"card_not_allowed",{entity:e.entity});if(n.status==="incomplete")return l(t,"card_timer_incomplete",{entity:e.entity});if(n.status==="found"&&it(n.info,n.info.ends_at))return l(t,"card_ends_at_disabled",{sensor:n.info.ends_at});if(n.status!=="not_found")return;let i=t.states[e.entity];return i===void 0?l(t,"card_entity_not_found",{entity:e.entity}):L(i)?l(t,"card_not_a_timer",{entity:e.entity}):void 0}render(){let t=this.#t,e=this._config;if(!t||!e)return c;let n=this.#v(t,e);if(n)return this.#a=void 0,u`
        <ha-card>
          <div class="warning" role="alert">
            <ha-icon icon="mdi:alert-outline"></ha-icon>
            <span>${n}</span>
          </div>
        </ha-card>
      `;let i=X(this._lookup),r=Se(t,e,this._lookup,i);return this.#a=r,u`
      ${e.layout==="round"?De(r,e,t,this.#r,this.#s,i):Oe(r,e,t,this.#r,this.#d,this.#s,i)}
      ${this._lookup.status==="found"?u`
            <timerify-card-popup
              .hass=${t}
              .config=${e}
              .lookup=${this._lookup}
              .view=${r}
              @closed=${()=>this.#f()}
            ></timerify-card-popup>
          `:c}
    `}};if(!customElements.get(Nt)){customElements.define("timerify-card-popup",pt),customElements.define(Nt,Ut);let o={type:Nt,name:"Timerify",description:l(void 0,"card_picker_description"),preview:!0,documentationURL:"https://github.com/klimofey/timerify#dashboard-card"};(window.customCards??=[]).push(o),ue(()=>{o.description=l(A(),"card_picker_description")})}export{Ut as TimerifyCard};
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
