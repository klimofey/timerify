var tt=globalThis,et=tt.ShadowRoot&&(tt.ShadyCSS===void 0||tt.ShadyCSS.nativeShadow)&&"adoptedStyleSheets"in Document.prototype&&"replace"in CSSStyleSheet.prototype,_t=Symbol(),zt=new WeakMap,I=class{constructor(t,e,o){if(this._$cssResult$=!0,o!==_t)throw Error("CSSResult is not constructable. Use `unsafeCSS` or `css` instead.");this.cssText=t,this.t=e}get styleSheet(){let t=this.o,e=this.t;if(et&&t===void 0){let o=e!==void 0&&e.length===1;o&&(t=zt.get(e)),t===void 0&&((this.o=t=new CSSStyleSheet).replaceSync(this.cssText),o&&zt.set(e,t))}return t}toString(){return this.cssText}},jt=n=>new I(typeof n=="string"?n:n+"",void 0,_t),_=(n,...t)=>{let e=n.length===1?n[0]:t.reduce((o,i,r)=>o+(s=>{if(s._$cssResult$===!0)return s.cssText;if(typeof s=="number")return s;throw Error("Value passed to 'css' function must be a 'css' function result: "+s+". Use 'unsafeCSS' to pass non-literal values, but take care to ensure page security.")})(i)+n[r+1],n[0]);return new I(e,n,_t)},Ft=(n,t)=>{if(et)n.adoptedStyleSheets=t.map(e=>e instanceof CSSStyleSheet?e:e.styleSheet);else for(let e of t){let o=document.createElement("style"),i=tt.litNonce;i!==void 0&&o.setAttribute("nonce",i),o.textContent=e.cssText,n.appendChild(o)}},gt=et?n=>n:n=>n instanceof CSSStyleSheet?(t=>{let e="";for(let o of t.cssRules)e+=o.cssText;return jt(e)})(n):n;var{is:Fe,defineProperty:Ve,getOwnPropertyDescriptor:Be,getOwnPropertyNames:We,getOwnPropertySymbols:Ke,getPrototypeOf:qe}=Object,nt=globalThis,Vt=nt.trustedTypes,Ge=Vt?Vt.emptyScript:"",Ye=nt.reactiveElementPolyfillSupport,z=(n,t)=>n,yt={toAttribute(n,t){switch(t){case Boolean:n=n?Ge:null;break;case Object:case Array:n=n==null?n:JSON.stringify(n)}return n},fromAttribute(n,t){let e=n;switch(t){case Boolean:e=n!==null;break;case Number:e=n===null?null:Number(n);break;case Object:case Array:try{e=JSON.parse(n)}catch{e=null}}return e}},Wt=(n,t)=>!Fe(n,t),Bt={attribute:!0,type:String,converter:yt,reflect:!1,useDefault:!1,hasChanged:Wt};Symbol.metadata??=Symbol("metadata"),nt.litPropertyMetadata??=new WeakMap;var w=class extends HTMLElement{static addInitializer(t){this._$Ei(),(this.l??=[]).push(t)}static get observedAttributes(){return this.finalize(),this._$Eh&&[...this._$Eh.keys()]}static createProperty(t,e=Bt){if(e.state&&(e.attribute=!1),this._$Ei(),this.prototype.hasOwnProperty(t)&&((e=Object.create(e)).wrapped=!0),this.elementProperties.set(t,e),!e.noAccessor){let o=Symbol(),i=this.getPropertyDescriptor(t,o,e);i!==void 0&&Ve(this.prototype,t,i)}}static getPropertyDescriptor(t,e,o){let{get:i,set:r}=Be(this.prototype,t)??{get(){return this[e]},set(s){this[e]=s}};return{get:i,set(s){let d=i?.call(this);r?.call(this,s),this.requestUpdate(t,d,o)},configurable:!0,enumerable:!0}}static getPropertyOptions(t){return this.elementProperties.get(t)??Bt}static _$Ei(){if(this.hasOwnProperty(z("elementProperties")))return;let t=qe(this);t.finalize(),t.l!==void 0&&(this.l=[...t.l]),this.elementProperties=new Map(t.elementProperties)}static finalize(){if(this.hasOwnProperty(z("finalized")))return;if(this.finalized=!0,this._$Ei(),this.hasOwnProperty(z("properties"))){let e=this.properties,o=[...We(e),...Ke(e)];for(let i of o)this.createProperty(i,e[i])}let t=this[Symbol.metadata];if(t!==null){let e=litPropertyMetadata.get(t);if(e!==void 0)for(let[o,i]of e)this.elementProperties.set(o,i)}this._$Eh=new Map;for(let[e,o]of this.elementProperties){let i=this._$Eu(e,o);i!==void 0&&this._$Eh.set(i,e)}this.elementStyles=this.finalizeStyles(this.styles)}static finalizeStyles(t){let e=[];if(Array.isArray(t)){let o=new Set(t.flat(1/0).reverse());for(let i of o)e.unshift(gt(i))}else t!==void 0&&e.push(gt(t));return e}static _$Eu(t,e){let o=e.attribute;return o===!1?void 0:typeof o=="string"?o:typeof t=="string"?t.toLowerCase():void 0}constructor(){super(),this._$Ep=void 0,this.isUpdatePending=!1,this.hasUpdated=!1,this._$Em=null,this._$Ev()}_$Ev(){this._$ES=new Promise(t=>this.enableUpdating=t),this._$AL=new Map,this._$E_(),this.requestUpdate(),this.constructor.l?.forEach(t=>t(this))}addController(t){(this._$EO??=new Set).add(t),this.renderRoot!==void 0&&this.isConnected&&t.hostConnected?.()}removeController(t){this._$EO?.delete(t)}_$E_(){let t=new Map,e=this.constructor.elementProperties;for(let o of e.keys())this.hasOwnProperty(o)&&(t.set(o,this[o]),delete this[o]);t.size>0&&(this._$Ep=t)}createRenderRoot(){let t=this.shadowRoot??this.attachShadow(this.constructor.shadowRootOptions);return Ft(t,this.constructor.elementStyles),t}connectedCallback(){this.renderRoot??=this.createRenderRoot(),this.enableUpdating(!0),this._$EO?.forEach(t=>t.hostConnected?.())}enableUpdating(t){}disconnectedCallback(){this._$EO?.forEach(t=>t.hostDisconnected?.())}attributeChangedCallback(t,e,o){this._$AK(t,o)}_$ET(t,e){let o=this.constructor.elementProperties.get(t),i=this.constructor._$Eu(t,o);if(i!==void 0&&o.reflect===!0){let r=(o.converter?.toAttribute!==void 0?o.converter:yt).toAttribute(e,o.type);this._$Em=t,r==null?this.removeAttribute(i):this.setAttribute(i,r),this._$Em=null}}_$AK(t,e){let o=this.constructor,i=o._$Eh.get(t);if(i!==void 0&&this._$Em!==i){let r=o.getPropertyOptions(i),s=typeof r.converter=="function"?{fromAttribute:r.converter}:r.converter?.fromAttribute!==void 0?r.converter:yt;this._$Em=i;let d=s.fromAttribute(e,r.type);this[i]=d??this._$Ej?.get(i)??d,this._$Em=null}}requestUpdate(t,e,o,i=!1,r){if(t!==void 0){let s=this.constructor;if(i===!1&&(r=this[t]),o??=s.getPropertyOptions(t),!((o.hasChanged??Wt)(r,e)||o.useDefault&&o.reflect&&r===this._$Ej?.get(t)&&!this.hasAttribute(s._$Eu(t,o))))return;this.C(t,e,o)}this.isUpdatePending===!1&&(this._$ES=this._$EP())}C(t,e,{useDefault:o,reflect:i,wrapped:r},s){o&&!(this._$Ej??=new Map).has(t)&&(this._$Ej.set(t,s??e??this[t]),r!==!0||s!==void 0)||(this._$AL.has(t)||(this.hasUpdated||o||(e=void 0),this._$AL.set(t,e)),i===!0&&this._$Em!==t&&(this._$Eq??=new Set).add(t))}async _$EP(){this.isUpdatePending=!0;try{await this._$ES}catch(e){Promise.reject(e)}let t=this.scheduleUpdate();return t!=null&&await t,!this.isUpdatePending}scheduleUpdate(){return this.performUpdate()}performUpdate(){if(!this.isUpdatePending)return;if(!this.hasUpdated){if(this.renderRoot??=this.createRenderRoot(),this._$Ep){for(let[i,r]of this._$Ep)this[i]=r;this._$Ep=void 0}let o=this.constructor.elementProperties;if(o.size>0)for(let[i,r]of o){let{wrapped:s}=r,d=this[i];s!==!0||this._$AL.has(i)||d===void 0||this.C(i,void 0,r,d)}}let t=!1,e=this._$AL;try{t=this.shouldUpdate(e),t?(this.willUpdate(e),this._$EO?.forEach(o=>o.hostUpdate?.()),this.update(e)):this._$EM()}catch(o){throw t=!1,this._$EM(),o}t&&this._$AE(e)}willUpdate(t){}_$AE(t){this._$EO?.forEach(e=>e.hostUpdated?.()),this.hasUpdated||(this.hasUpdated=!0,this.firstUpdated(t)),this.updated(t)}_$EM(){this._$AL=new Map,this.isUpdatePending=!1}get updateComplete(){return this.getUpdateComplete()}getUpdateComplete(){return this._$ES}shouldUpdate(t){return!0}update(t){this._$Eq&&=this._$Eq.forEach(e=>this._$ET(e,this[e])),this._$EM()}updated(t){}firstUpdated(t){}};w.elementStyles=[],w.shadowRootOptions={mode:"open"},w[z("elementProperties")]=new Map,w[z("finalized")]=new Map,Ye?.({ReactiveElement:w}),(nt.reactiveElementVersions??=[]).push("2.1.2");var Ct=globalThis,Kt=n=>n,ot=Ct.trustedTypes,qt=ot?ot.createPolicy("lit-html",{createHTML:n=>n}):void 0,Qt="$lit$",C=`lit$${Math.random().toFixed(9).slice(2)}$`,te="?"+C,Xe=`<${te}>`,T=document,F=()=>T.createComment(""),V=n=>n===null||typeof n!="object"&&typeof n!="function",Et=Array.isArray,Ze=n=>Et(n)||typeof n?.[Symbol.iterator]=="function",bt=`[ 	
\f\r]`,j=/<(?:(!--|\/[^a-zA-Z])|(\/?[a-zA-Z][^>\s]*)|(\/?$))/g,Gt=/-->/g,Yt=/>/g,S=RegExp(`>|${bt}(?:([^\\s"'>=/]+)(${bt}*=${bt}*(?:[^ 	
\f\r"'\`<>=]|("|')|))|$)`,"g"),Xt=/'/g,Zt=/"/g,ee=/^(?:script|style|textarea|title)$/i,St=n=>(t,...e)=>({_$litType$:n,strings:t,values:e}),u=St(1),Mn=St(2),Ln=St(3),x=Symbol.for("lit-noChange"),c=Symbol.for("lit-nothing"),Jt=new WeakMap,k=T.createTreeWalker(T,129);function ne(n,t){if(!Et(n)||!n.hasOwnProperty("raw"))throw Error("invalid template strings array");return qt!==void 0?qt.createHTML(t):t}var Je=(n,t)=>{let e=n.length-1,o=[],i,r=t===2?"<svg>":t===3?"<math>":"",s=j;for(let d=0;d<e;d++){let a=n[d],h,f,p=-1,g=0;for(;g<a.length&&(s.lastIndex=g,f=s.exec(a),f!==null);)g=s.lastIndex,s===j?f[1]==="!--"?s=Gt:f[1]!==void 0?s=Yt:f[2]!==void 0?(ee.test(f[2])&&(i=RegExp("</"+f[2],"g")),s=S):f[3]!==void 0&&(s=S):s===S?f[0]===">"?(s=i??j,p=-1):f[1]===void 0?p=-2:(p=s.lastIndex-f[2].length,h=f[1],s=f[3]===void 0?S:f[3]==='"'?Zt:Xt):s===Zt||s===Xt?s=S:s===Gt||s===Yt?s=j:(s=S,i=void 0);let y=s===S&&n[d+1].startsWith("/>")?" ":"";r+=s===j?a+Xe:p>=0?(o.push(h),a.slice(0,p)+Qt+a.slice(p)+C+y):a+C+(p===-2?d:y)}return[ne(n,r+(n[e]||"<?>")+(t===2?"</svg>":t===3?"</math>":"")),o]},B=class n{constructor({strings:t,_$litType$:e},o){let i;this.parts=[];let r=0,s=0,d=t.length-1,a=this.parts,[h,f]=Je(t,e);if(this.el=n.createElement(h,o),k.currentNode=this.el.content,e===2||e===3){let p=this.el.content.firstChild;p.replaceWith(...p.childNodes)}for(;(i=k.nextNode())!==null&&a.length<d;){if(i.nodeType===1){if(i.hasAttributes())for(let p of i.getAttributeNames())if(p.endsWith(Qt)){let g=f[s++],y=i.getAttribute(p).split(C),E=/([.?@])?(.*)/.exec(g);a.push({type:1,index:r,name:E[2],strings:y,ctor:E[1]==="."?$t:E[1]==="?"?wt:E[1]==="@"?xt:R}),i.removeAttribute(p)}else p.startsWith(C)&&(a.push({type:6,index:r}),i.removeAttribute(p));if(ee.test(i.tagName)){let p=i.textContent.split(C),g=p.length-1;if(g>0){i.textContent=ot?ot.emptyScript:"";for(let y=0;y<g;y++)i.append(p[y],F()),k.nextNode(),a.push({type:2,index:++r});i.append(p[g],F())}}}else if(i.nodeType===8)if(i.data===te)a.push({type:2,index:r});else{let p=-1;for(;(p=i.data.indexOf(C,p+1))!==-1;)a.push({type:7,index:r}),p+=C.length-1}r++}}static createElement(t,e){let o=T.createElement("template");return o.innerHTML=t,o}};function P(n,t,e=n,o){if(t===x)return t;let i=o!==void 0?e._$Co?.[o]:e._$Cl,r=V(t)?void 0:t._$litDirective$;return i?.constructor!==r&&(i?._$AO?.(!1),r===void 0?i=void 0:(i=new r(n),i._$AT(n,e,o)),o!==void 0?(e._$Co??=[])[o]=i:e._$Cl=i),i!==void 0&&(t=P(n,i._$AS(n,t.values),i,o)),t}var vt=class{constructor(t,e){this._$AV=[],this._$AN=void 0,this._$AD=t,this._$AM=e}get parentNode(){return this._$AM.parentNode}get _$AU(){return this._$AM._$AU}u(t){let{el:{content:e},parts:o}=this._$AD,i=(t?.creationScope??T).importNode(e,!0);k.currentNode=i;let r=k.nextNode(),s=0,d=0,a=o[0];for(;a!==void 0;){if(s===a.index){let h;a.type===2?h=new W(r,r.nextSibling,this,t):a.type===1?h=new a.ctor(r,a.name,a.strings,this,t):a.type===6&&(h=new At(r,this,t)),this._$AV.push(h),a=o[++d]}s!==a?.index&&(r=k.nextNode(),s++)}return k.currentNode=T,i}p(t){let e=0;for(let o of this._$AV)o!==void 0&&(o.strings!==void 0?(o._$AI(t,o,e),e+=o.strings.length-2):o._$AI(t[e])),e++}},W=class n{get _$AU(){return this._$AM?._$AU??this._$Cv}constructor(t,e,o,i){this.type=2,this._$AH=c,this._$AN=void 0,this._$AA=t,this._$AB=e,this._$AM=o,this.options=i,this._$Cv=i?.isConnected??!0}get parentNode(){let t=this._$AA.parentNode,e=this._$AM;return e!==void 0&&t?.nodeType===11&&(t=e.parentNode),t}get startNode(){return this._$AA}get endNode(){return this._$AB}_$AI(t,e=this){t=P(this,t,e),V(t)?t===c||t==null||t===""?(this._$AH!==c&&this._$AR(),this._$AH=c):t!==this._$AH&&t!==x&&this._(t):t._$litType$!==void 0?this.$(t):t.nodeType!==void 0?this.T(t):Ze(t)?this.k(t):this._(t)}O(t){return this._$AA.parentNode.insertBefore(t,this._$AB)}T(t){this._$AH!==t&&(this._$AR(),this._$AH=this.O(t))}_(t){this._$AH!==c&&V(this._$AH)?this._$AA.nextSibling.data=t:this.T(T.createTextNode(t)),this._$AH=t}$(t){let{values:e,_$litType$:o}=t,i=typeof o=="number"?this._$AC(t):(o.el===void 0&&(o.el=B.createElement(ne(o.h,o.h[0]),this.options)),o);if(this._$AH?._$AD===i)this._$AH.p(e);else{let r=new vt(i,this),s=r.u(this.options);r.p(e),this.T(s),this._$AH=r}}_$AC(t){let e=Jt.get(t.strings);return e===void 0&&Jt.set(t.strings,e=new B(t)),e}k(t){Et(this._$AH)||(this._$AH=[],this._$AR());let e=this._$AH,o,i=0;for(let r of t)i===e.length?e.push(o=new n(this.O(F()),this.O(F()),this,this.options)):o=e[i],o._$AI(r),i++;i<e.length&&(this._$AR(o&&o._$AB.nextSibling,i),e.length=i)}_$AR(t=this._$AA.nextSibling,e){for(this._$AP?.(!1,!0,e);t!==this._$AB;){let o=Kt(t).nextSibling;Kt(t).remove(),t=o}}setConnected(t){this._$AM===void 0&&(this._$Cv=t,this._$AP?.(t))}},R=class{get tagName(){return this.element.tagName}get _$AU(){return this._$AM._$AU}constructor(t,e,o,i,r){this.type=1,this._$AH=c,this._$AN=void 0,this.element=t,this.name=e,this._$AM=i,this.options=r,o.length>2||o[0]!==""||o[1]!==""?(this._$AH=Array(o.length-1).fill(new String),this.strings=o):this._$AH=c}_$AI(t,e=this,o,i){let r=this.strings,s=!1;if(r===void 0)t=P(this,t,e,0),s=!V(t)||t!==this._$AH&&t!==x,s&&(this._$AH=t);else{let d=t,a,h;for(t=r[0],a=0;a<r.length-1;a++)h=P(this,d[o+a],e,a),h===x&&(h=this._$AH[a]),s||=!V(h)||h!==this._$AH[a],h===c?t=c:t!==c&&(t+=(h??"")+r[a+1]),this._$AH[a]=h}s&&!i&&this.j(t)}j(t){t===c?this.element.removeAttribute(this.name):this.element.setAttribute(this.name,t??"")}},$t=class extends R{constructor(){super(...arguments),this.type=3}j(t){this.element[this.name]=t===c?void 0:t}},wt=class extends R{constructor(){super(...arguments),this.type=4}j(t){this.element.toggleAttribute(this.name,!!t&&t!==c)}},xt=class extends R{constructor(t,e,o,i,r){super(t,e,o,i,r),this.type=5}_$AI(t,e=this){if((t=P(this,t,e,0)??c)===x)return;let o=this._$AH,i=t===c&&o!==c||t.capture!==o.capture||t.once!==o.once||t.passive!==o.passive,r=t!==c&&(o===c||i);i&&this.element.removeEventListener(this.name,this,o),r&&this.element.addEventListener(this.name,this,t),this._$AH=t}handleEvent(t){typeof this._$AH=="function"?this._$AH.call(this.options?.host??this.element,t):this._$AH.handleEvent(t)}},At=class{constructor(t,e,o){this.element=t,this.type=6,this._$AN=void 0,this._$AM=e,this.options=o}get _$AU(){return this._$AM._$AU}_$AI(t){P(this,t)}};var Qe=Ct.litHtmlPolyfillSupport;Qe?.(B,W),(Ct.litHtmlVersions??=[]).push("3.3.3");var oe=(n,t,e)=>{let o=e?.renderBefore??t,i=o._$litPart$;if(i===void 0){let r=e?.renderBefore??null;o._$litPart$=i=new W(t.insertBefore(F(),r),r,void 0,e??{})}return i._$AI(n),i};var kt=globalThis,b=class extends w{constructor(){super(...arguments),this.renderOptions={host:this},this._$Do=void 0}createRenderRoot(){let t=super.createRenderRoot();return this.renderOptions.renderBefore??=t.firstChild,t}update(t){let e=this.render();this.hasUpdated||(this.renderOptions.isConnected=this.isConnected),super.update(t),this._$Do=oe(e,this.renderRoot,this.renderOptions)}connectedCallback(){super.connectedCallback(),this._$Do?.setConnected(!0)}disconnectedCallback(){super.disconnectedCallback(),this._$Do?.setConnected(!1)}render(){return x}};b._$litElement$=!0,b.finalized=!0,kt.litElementHydrateSupport?.({LitElement:b});var tn=kt.litElementPolyfillSupport;tn?.({LitElement:b});(kt.litElementVersions??=[]).push("4.2.2");async function H(n,t,e,o,i){try{await n.callService(t,e,o,{entity_id:i})}catch{}}function ie(n,t,e){return H(n,"number","set_value",{value:e},t)}function K(n,t,e){return H(n,"timerify","add_time",{minutes:e},t)}function Tt(n,t){return H(n,"timerify","run",{},t)}function O(n,t){return H(n,"timerify","stop",{},t)}function re(n,t,e){return H(n,"switch",e?"turn_on":"turn_off",{},t)}function se(n,t,e){return H(n,"timerify","cancel_command",{command_id:e},t)}var ae={card_entity_not_found:"Entity not found: {entity}",card_not_a_timer:"{entity} is not the Run for number of a Timerify timer",card_timer_incomplete:"The timer of {entity} cannot be shown: its target or one of its sensors is missing. Open the timer's page to see why.",card_not_allowed:"You are not allowed to see the timer {entity}",card_ends_at_disabled:"The Ends at sensor of this timer, {sensor}, is disabled. Enable it for the card to work",card_error_entity:"Choose the Run for number of a timer",card_error_layout:"The layout is pill or round",card_error_presets:"Presets are whole minutes from 1 to 1440",card_error_chip:"The quick chip is whole minutes from 1 to 1440",card_error_press:"Tap, double tap and hold can each be popup, run, stop, run_or_stop, action or none",card_error_action:"A Home Assistant action is a set of settings, such as action: more-info",card_error_show_turn_off:"show_turn_off is true or false",card_close:"Close",card_until:"until {time}",card_add_time:"Add {duration}",card_subtract_time:"Take off {duration}",card_stop:"Stop",card_turn_off:"Turn off",card_schedule:"Schedule",card_commands:"Pending commands",card_commands_disabled:"Pending commands are hidden: the Next command sensor, {sensor}, is disabled",card_command_on:"On at {time}",card_command_on_for:"On at {time} for {duration}",card_command_off:"Off at {time}",card_cancel_command:"Cancel",card_settings:"Settings",card_picker_description:"The countdown, presets and schedule of a Timerify timer",card_editor_entity:"Timer",card_editor_layout:"Layout",card_editor_layout_pill:"Pill",card_editor_layout_round:"Round",card_editor_name:"Name",card_editor_icon:"Icon",card_editor_presets:"Duration presets (minutes)",card_editor_presets_helper:"Leave empty for {presets}",card_editor_chip:"Quick add chip (minutes, pill only)",card_editor_show_turn_off:"Show a Turn off button",card_editor_interactions:"Interactions",card_editor_tap:"Tap behavior",card_editor_double_tap:"Double tap behavior",card_editor_hold:"Hold behavior",card_editor_tap_action:"Tap action",card_editor_double_tap_action:"Double tap action",card_editor_hold_action:"Hold action",card_editor_press_popup:"Open the pop-up",card_editor_press_run:"Run for the default duration",card_editor_press_stop:"Stop",card_editor_press_run_or_stop:"Start or stop",card_editor_press_action:"Home Assistant action",card_editor_press_none:"Nothing",card_editor_action_helper:'Used when the behavior above is set to "Home Assistant action"'};var ce="common",le="timerify",en=`component.${le}.${ce}.`;function Pt(n){return en+n}function nn(n,t){return n.replace(/\{(\w+)\}/g,(e,o)=>String(t?.[o]??e))}function l(n,t,e){return n?.localize(Pt(t),e)||nn(ae[t],e)}var q,de=Promise.resolve(),ue,pe=new Set;function it(n){return n.language!==q&&(q=n.language,de=on(n,n.language)),de}async function on(n,t){let e;try{e=await n.loadBackendTranslation(ce,le)}catch{q===t&&(q=void 0);return}q===t&&(ue={...n,localize:e},pe.forEach(o=>o()))}function A(){return ue}function he(n){pe.add(n)}var G=[15,30,45,60,120],Ht=1440,Ot=["popup","run","stop","run_or_stop","action","none"],rn=["tap","double_tap","hold"],Mt=["tap_action","double_tap_action","hold_action"],m=class extends Error{constructor(e){super(l(A(),e));this.key=e}key};function me(n){let t=typeof n=="number"?n:typeof n=="string"&&/^\d+$/.test(n)?Number(n):void 0;return t!==void 0&&Number.isInteger(t)&&t>=1&&t<=Ht?t:void 0}function sn(n){if(n===void 0||Array.isArray(n)&&n.length===0)return[...G];if(!Array.isArray(n))throw new m("card_error_presets");let t=new Set;for(let e of n){let o=me(e);if(o===void 0)throw new m("card_error_presets");t.add(o)}return[...t]}function an(n){if(n===void 0)return;let t=me(n);if(t===void 0)throw new m("card_error_chip");return t}var _e=n=>typeof n=="object"&&n!==null?n:{},dn=n=>Ot.some(t=>t===n);function Rt(n,t){if(n===void 0)return t;if(!dn(n))throw new m("card_error_press");return n}function cn(n){if(n===void 0)return!1;if(typeof n!="boolean")throw new m("card_error_show_turn_off");return n}var ln=n=>typeof n=="object"&&n!==null&&!Array.isArray(n);function ge(n){let t={};for(let e of Mt){let o=n[e];if(o!==void 0){if(!ln(o))throw new m("card_error_action");t[e]=o}}return t}var fe=n=>typeof n=="number"||typeof n=="string";function ye(n){let t=_e(n),{entity:e,layout:o,presets:i,chip:r}=t;if(e!==void 0&&typeof e!="string")throw new m("card_error_entity");if(o!==void 0&&typeof o!="string")throw new m("card_error_layout");if(i!==void 0&&!(Array.isArray(i)&&i.every(fe)))throw new m("card_error_presets");if(r!==void 0&&!fe(r))throw new m("card_error_chip");if(t.show_turn_off!==void 0&&typeof t.show_turn_off!="boolean")throw new m("card_error_show_turn_off");for(let s of rn)if(t[s]!==void 0&&typeof t[s]!="string")throw new m("card_error_press");ge(t)}function be(n){let t=_e(n),{entity:e,layout:o="pill",name:i,icon:r}=t;if(typeof e!="string"||!/^number\.[a-z0-9_]+$/.test(e))throw new m("card_error_entity");if(o!=="pill"&&o!=="round")throw new m("card_error_layout");let s=an(t.chip);return{entity:e,layout:o,...typeof i=="string"&&i!==""&&{name:i},...typeof r=="string"&&r!==""&&{icon:r},presets:sn(t.presets),...s!==void 0&&{chip:s},show_turn_off:cn(t.show_turn_off),tap:Rt(t.tap,"popup"),double_tap:Rt(t.double_tap,"none"),hold:Rt(t.hold,o==="round"?"run_or_stop":"none"),...ge(t)}}var rt=class{#t;#e;#n;#o=!1;#i;constructor(t,e,o){this.#t=t,this.#e=e,this.#n=o,t.addController(this)}hostConnected(){this.#o=!0,this.#r()}hostUpdated(){this.#r()}hostDisconnected(){this.#o=!1,this.#r()}#r(){let t=this.#e(),e=this.#o&&t!==void 0&&t.getTime()>this.#n();e&&this.#i===void 0?this.#i=setInterval(()=>this.#t.requestUpdate(),1e3):!e&&this.#i!==void 0&&(clearInterval(this.#i),this.#i=void 0)}};var ve=n=>String(n).padStart(2,"0");function M(n){let t=Math.ceil(Math.max(0,n)),e=Math.floor(t/3600),o=Math.floor(t%3600/60),i=ve(t%60);return e>0?`${e}:${ve(o)}:${i}`:`${o}:${i}`}function un({language:n,time_format:t}){if(t==="12"||t==="24")return t==="12";let e=new Intl.DateTimeFormat(t==="language"?n:void 0,{hour:"numeric"}).resolvedOptions();return e.hourCycle==="h11"||e.hourCycle==="h12"}var pn=864e5;function $e(n,t){let e=new Intl.DateTimeFormat("en-US",{timeZone:n,year:"numeric",month:"numeric",day:"numeric"}).formatToParts(t),o=i=>Number(e.find(r=>r.type===i)?.value);return Date.UTC(o("year"),o("month")-1,o("day"))/pn}function Y(n,t,e){let{locale:o}=n,i=o.time_zone==="server"?n.config.time_zone:void 0,r=$e(i,t.getTime())-$e(i,e),s=r===0?{}:r>=1&&r<=6?{weekday:"short"}:{month:"short",day:"numeric"};return new Intl.DateTimeFormat(o.language,{...s,hour:"numeric",minute:"2-digit",hourCycle:un(o)?"h12":"h23",timeZone:i}).format(t)}function v(n,t){let e=(s,d)=>new Intl.NumberFormat(n.locale.language,{style:"unit",unit:d,unitDisplay:"short",useGrouping:!1}).format(s),o=Math.floor(t/60),i=t%60,r=o>0?[e(o,"hour")]:[];return(i>0||o===0)&&r.push(e(i,"minute")),r.join(" ")}function we(n,t,e,o,i){return e.includes(o)&&typeof i=="number"?new Intl.NumberFormat(n.locale.language,{style:"percent",maximumFractionDigits:1}).format(i/100):t===void 0?String(i):o==="hvac_mode"?n.formatEntityState(t,String(i)):n.formatEntityAttributeValue(t,o,i)}var xe={entity:"card_editor_entity",layout:"card_editor_layout",name:"card_editor_name",icon:"card_editor_icon",presets:"card_editor_presets",chip:"card_editor_chip",show_turn_off:"card_editor_show_turn_off",interactions:"card_editor_interactions",tap:"card_editor_tap",double_tap:"card_editor_double_tap",hold:"card_editor_hold",tap_action:"card_editor_tap_action",double_tap_action:"card_editor_double_tap_action",hold_action:"card_editor_hold_action"},hn={popup:"card_editor_press_popup",run:"card_editor_press_run",stop:"card_editor_press_stop",run_or_stop:"card_editor_press_run_or_stop",action:"card_editor_press_action",none:"card_editor_press_none"},fn=n=>Object.hasOwn(xe,n),mn=n=>n.endsWith("_action"),_n={locale:{language:"en"}};function Ae(){return A()??_n}function gn(){let n=Ae();return new Intl.ListFormat(n.locale.language,{style:"long",type:"conjunction"}).format(G.map(t=>v(n,t)))}async function Ce(){let n=A(),t=Ot.map(e=>({value:e,label:l(n,hn[e])}));return{schema:[{name:"entity",required:!0,selector:{entity:{filter:{integration:"timerify",domain:"number"}}}},{name:"layout",selector:{select:{options:[{value:"pill",label:l(n,"card_editor_layout_pill")},{value:"round",label:l(n,"card_editor_layout_round")}]}}},{name:"",type:"grid",schema:[{name:"name",selector:{text:{}}},{name:"icon",selector:{icon:{}}}]},{name:"presets",selector:{select:{multiple:!0,custom_value:!0,options:G.map(e=>({value:String(e),label:v(Ae(),e)}))}}},{name:"chip",selector:{number:{min:1,max:Ht,mode:"box"}}},{name:"show_turn_off",selector:{boolean:{}}},{name:"interactions",type:"expandable",flatten:!0,icon:"mdi:gesture-tap",schema:[{name:"tap",selector:{select:{options:t}}},{name:"tap_action",selector:{ui_action:{default_action:"more-info"}}},{name:"double_tap",selector:{select:{options:t}}},{name:"double_tap_action",selector:{ui_action:{default_action:"more-info"}}},{name:"hold",selector:{select:{options:t}}},{name:"hold_action",selector:{ui_action:{default_action:"more-info"}}}]}],assertConfig:ye,computeLabel:({name:e},o)=>fn(e)?o(Pt(xe[e])):"",computeHelper:({name:e})=>e==="presets"?l(A(),"card_editor_presets_helper",{presets:gn()}):mn(e)?l(A(),"card_editor_action_helper"):void 0}}function Ee(n,t,e){it(n);let o=r=>{let s=n.entities[r];return s?.platform==="timerify"&&s.translation_key==="run_for"},i=r=>r.filter(o).sort()[0];return{entity:i(t)??i(e)??i(Object.keys(n.entities))??"",layout:"pill",presets:G.map(String)}}var yn="not_found",bn="timer_incomplete",vn="unauthorized";async function ke(n,t){let e=Date.now();try{let o=await n.callWS({type:"timerify/timer",entity_id:t}),i=Lt(o.server_time),r=i===void 0?0:i-(e+Date.now())/2;return{status:"found",info:o,clockOffset:r}}catch(o){let i=typeof o=="object"&&o!==null&&"code"in o?o.code:"";return i===yn?{status:"not_found"}:i===bn?{status:"incomplete"}:{status:i===vn?"unauthorized":"failed"}}}var X=n=>Date.now()+(n.status==="found"?n.clockOffset:0),st=(n,t)=>n.disabled_sensors.includes(t),L=n=>n!==void 0&&n.state!=="unavailable"&&n.state!=="unknown";function $n(n,t){return n===void 0||n.state==="unavailable"||n.state==="unknown"?!1:t.states.includes(n.state)===(t.match==="is")}var wn="mdi:timer-outline",Se=n=>n===void 0||n.state==="unavailable";function Lt(n){let t=typeof n=="string"?Date.parse(n):Number.NaN;return Number.isNaN(t)?void 0:t}function Te(n,t,e,o){let i=e.status==="found"?e.info:void 0,r=n.states[t.entity],s=i&&n.states[i.target],d=t.name||s&&n.formatEntityName(s,void 0)||r?.attributes.friendly_name||t.entity,a=t.icon?{icon:t.icon}:s?{stateObj:s}:{icon:wn},h={name:d,icon:a,target:s,remaining:0},f=i&&n.states[i.ends_at];if(i===void 0||f===void 0||Se(r)||Se(f))return{...h,state:"unavailable",progress:0};let p=Lt(f.state);if(p===void 0)return $n(s,i.target_on)?{...h,state:"open",progress:1}:{...h,state:"idle",progress:0};let g=Lt(f.attributes.started_at),y=g===void 0?0:(p-g)/1e3,E=Math.max(0,(p-o)/1e3);return{...h,state:"counting",remaining:E,progress:y>0?Math.min(1,E/y):1,endsAt:new Date(p)}}var N=({state:n})=>n==="counting"||n==="open";function at(n,t){return t?[n,t.ends_at,t.next_command,t.target,...t.intervals.map(({entity_id:e})=>e)]:[n]}var xn=["locale","language","localize","config","user","connected","entities","formatEntityName","formatEntityState","formatEntityAttributeValue"];function dt(n,t,e){for(let i of n.keys())if(i!=="hass")return!0;let o=n.get("hass");return o===void 0||t===void 0?!0:xn.some(i=>o[i]!==t[i])||e.some(i=>o.states[i]!==t.states[i])}function ct(n){return"stateObj"in n.icon?u`<ha-state-icon .stateObj=${n.icon.stateObj}></ha-state-icon>`:u`<ha-icon .icon=${n.icon.icon}></ha-icon>`}var lt=n=>n.tap==="popup"?"dialog":void 0,U=n=>n.tap!=="none"||n.double_tap!=="none"||n.hold!=="none";function ut(n,t,e,o){if(!t.show_turn_off||!N(n))return c;let i=l(e,"card_turn_off");return u`
    <button class="turn-off" type="button" aria-label=${i} title=${i} @click=${o}>
      <ha-icon class="turn-off-icon" icon="mdi:power"></ha-icon>
      <span class="turn-off-label">${i}</span>
    </button>
  `}var Z={pill:245,pillWithChip:335,round:101},J=n=>_`
  ${n} .turn-off {
    width: 40px;
    height: 40px;
    padding: 0;
    border-radius: 20px;
  }
  ${n} .turn-off-label {
    display: none;
  }
  ${n} .turn-off-icon {
    display: flex;
  }
`;function An(n,t,e){if(n.state!=="unavailable")return n.target?e.formatEntityState(n.target):"";let o=e.states[t.entity];if(L(o))return"";let i={entity_id:t.entity,state:"unavailable",attributes:{}};return e.formatEntityState(o??i,"unavailable")}function pt(n,t,e,o){if(n.state!=="counting"||n.endsAt===void 0)return An(n,t,e);let i=Y(e,n.endsAt,o);return u`
    <span class="remaining">${M(n.remaining)}</span>
    <span class="until">${l(e,"card_until",{time:i})}</span>
  `}var Pe=_`
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
    /* The width of the content is what the Turn off button chooses its form by. */
    container-type: inline-size;
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
  .turn-off {
    display: inline-flex;
    align-items: center;
    justify-content: center;
  }
  /* The words by default; a narrow card shows the icon instead, see turnOffAsIcon. */
  .turn-off-icon {
    --mdc-icon-size: 24px;
    display: none;
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
`;var $=n=>n??c;var Re={ATTRIBUTE:1,CHILD:2,PROPERTY:3,BOOLEAN_ATTRIBUTE:4,EVENT:5,ELEMENT:6},He=n=>(...t)=>({_$litDirective$:n,values:t}),ht=class{constructor(t){}get _$AU(){return this._$AM._$AU}_$AT(t,e,o){this._$Ct=t,this._$AM=e,this._$Ci=o}_$AS(t,e){return this.update(t,e)}update(t,e){return this.render(...e)}};var Oe="important",Cn=" !"+Oe,Me=He(class extends ht{constructor(n){if(super(n),n.type!==Re.ATTRIBUTE||n.name!=="style"||n.strings?.length>2)throw Error("The `styleMap` directive must be used in the `style` attribute and must be the only part in the attribute.")}render(n){return Object.keys(n).reduce((t,e)=>{let o=n[e];return o==null?t:t+`${e=e.includes("-")?e:e.replace(/(?:^(webkit|moz|ms|o)|)(?=[A-Z])/g,"-$&").toLowerCase()}:${o};`},"")}update(n,[t]){let{style:e}=n.element;if(this.ft===void 0)return this.ft=new Set(Object.keys(t)),this.render(t);for(let o of this.ft)t[o]==null&&(this.ft.delete(o),o.includes("-")?e.removeProperty(o):e[o]=null);for(let o in t){let i=t[o];if(i!=null){this.ft.add(o);let r=typeof i=="string"&&i.endsWith(Cn);o.includes("-")||r?e.setProperty(o,r?i.slice(0,-11):i,r?Oe:""):e[o]=i}}return x}});function Le(n,t,e,o,i,r,s){let d=Math.round(n.progress*1e3)/10,a=U(t);return u`
    <ha-card class="pill ${n.state} ${t.chip===void 0?"":"with-chip"}">
      <div
        class="body"
        role=${$(a?"button":void 0)}
        tabindex=${$(a?"0":void 0)}
        aria-haspopup=${$(lt(t))}
        aria-labelledby=${$(a?"label":void 0)}
        @click=${o.click}
        @keydown=${o.keydown}
        @keyup=${o.keyup}
        @pointerdown=${o.pointerdown}
        @pointerup=${o.pointerup}
        @pointercancel=${o.pointercancel}
        @pointerleave=${o.pointerleave}
        @contextmenu=${o.contextmenu}
      >
        <span class="fill-clip" aria-hidden="true">
          <span class="fill" style=${Me({width:`${d}%`})}></span>
        </span>
      </div>
      <div class="content">
        <span class="icon">${ct(n)}</span>
        <span class="text" id="label">
          <span class="name">${n.name}</span>
          <span class="status">${pt(n,t,e,s)}</span>
        </span>
        ${ut(n,t,e,r)}
        ${t.chip===void 0?c:u`
              <button
                class="chip"
                type="button"
                aria-label=${l(e,"card_add_time",{duration:v(e,t.chip)})}
                ?disabled=${n.state==="unavailable"}
                @click=${i}
              >
                +${v(e,t.chip)}
              </button>
            `}
      </div>
    </ha-card>
  `}var Ne=_`
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
  /* The room the words of Turn off need: the icon, the name, the button, and the chip. */
  @container (width < ${Z.pill}px) {
    ${J(_`.pill`)}
  }
  @container (width < ${Z.pillWithChip}px) {
    ${J(_`.pill.with-chip`)}
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
`;function En(n,t){let e=t?.attributes.max;return typeof e=="number"&&Number.isFinite(e)?n.filter(o=>o<=e):[...n]}function Sn(n){let t=n?.attributes.commands;return Array.isArray(t)?t.flatMap(e=>{if(typeof e!="object"||e===null)return[];let{id:o,at:i,action:r,minutes:s,settings:d}=e,a=typeof i=="string"?new Date(i):void 0;return typeof o!="string"||a===void 0||Number.isNaN(a.getTime())||r!=="on"&&r!=="off"?[]:[{id:o,at:a,action:r,minutes:typeof s=="number"&&s>0?s:null,settings:typeof d=="object"&&d!==null?Object.entries(d):[]}]}):[]}var kn=n=>`/config/integrations/integration/timerify#config_entry=${encodeURIComponent(n)}`,ft=class extends b{static properties={hass:{attribute:!1},config:{attribute:!1},lookup:{attribute:!1},view:{attribute:!1},opened:{state:!0}};static styles=_`
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
  `;constructor(){super(),this.opened=!1}open(){this.opened=!0}close(){this.#t?.close(),this.#s()}disconnectedCallback(){super.disconnectedCallback(),this.close()}get#t(){return this.renderRoot.querySelector("dialog")}#e=()=>{this.#t?.open||this.#s()};#n=!1;#o=t=>{this.#n=t.target===t.currentTarget};#i=t=>{this.#n&&=t.target===t.currentTarget};#r=()=>{this.#n=!1};#d=t=>{let e=this.#n&&t.target===t.currentTarget;this.#n=!1,e&&this.close()};#s(){this.opened&&(this.opened=!1,this.dispatchEvent(new CustomEvent("closed")))}shouldUpdate(t){if(!this.hasUpdated||t.has("opened"))return!0;let e=at(this.config.entity,this.lookup.info);return this.opened&&dt(t,this.hass,e)}updated(t){let e=this.#t;t.has("opened")&&this.opened&&e&&!e.open&&e.showModal()}render(){return u`
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
    `}#a(){let{hass:t,view:e}=this,o=X(this.lookup);return u`
      <div class="wrapper">
        <header>
          <h2 id="title">${e.name}</h2>
          <button class="close" @click=${()=>this.close()}>${l(t,"card_close")}</button>
        </header>
        ${this.#u(o)} ${this.#p()} ${this.#h()} ${this.#c(o)}
        ${this.#m()}
      </div>
    `}#u(t){let{hass:e,view:o}=this;if(o.state!=="counting"||o.endsAt===void 0)return c;let i=Y(e,o.endsAt,t);return u`
      <p class="countdown">
        <span class="remaining">${M(o.remaining)}</span>
        <span class="until">${l(e,"card_until",{time:i})}</span>
      </p>
    `}#p(){let{hass:t,config:e,view:o}=this,i=v(t,5),r=o.state==="counting",s=N(o),d=o.state==="unavailable",a=En(e.presets,t.states[e.entity]);return u`
      ${a.length===0?c:u`
            <div class="presets">
              ${a.map(h=>u`
                  <button
                    class="action preset"
                    ?disabled=${d}
                    @click=${()=>{ie(t,e.entity,h)}}
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
          @click=${()=>{K(t,e.entity,-5)}}
        >
          −${i}
        </button>
        <button
          class="action step"
          aria-label=${l(t,"card_add_time",{duration:i})}
          ?disabled=${d}
          @click=${()=>{K(t,e.entity,5)}}
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
    `}#l({entity_id:t,title:e}){let{hass:o}=this,i=o.states[t],r=i!==void 0&&i.state!=="unavailable",s=r&&i.state==="on",d=i??{entity_id:t,state:"unavailable",attributes:{}};return u`
      <button
        class="interval"
        role="switch"
        aria-checked=${s?"true":"false"}
        ?disabled=${!r}
        @click=${()=>{re(o,t,!s)}}
      >
        <span class="label">
          <span class="title">${e}</span>
          ${r?c:u`<span class="state">${o.formatEntityState(d,"unavailable")}</span>`}
        </span>
        <span class="track" aria-hidden="true"><span class="knob"></span></span>
      </button>
    `}#c(t){let{hass:e,config:o,view:i}=this,{info:r}=this.lookup;if(st(r,r.next_command))return u`
        <section class="commands">
          <p class="note">${l(e,"card_commands_disabled",{sensor:r.next_command})}</p>
        </section>
      `;let s=Sn(e.states[r.next_command]);if(s.length===0)return c;let d=i.state==="unavailable";return u`
      <section class="commands">
        <h3>${l(e,"card_commands")}</h3>
        <ul>
          ${s.map((a,h)=>{let f=a.settings.map(([p,g])=>we(e,i.target,r.percent_settings,p,g));return u`
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
                  @click=${()=>{se(e,o.entity,a.id)}}
                >
                  <span aria-hidden="true">×</span>
                </button>
              </li>
            `})}
        </ul>
      </section>
    `}#f(t,e){let{hass:o}=this,i=Y(o,t.at,e);return t.action==="off"?l(o,"card_command_off",{time:i}):t.minutes===null?l(o,"card_command_on",{time:i}):l(o,"card_command_on_for",{time:i,duration:v(o,t.minutes)})}#m(){return this.hass.user?.is_admin?u`
      <footer>
        <a href=${kn(this.lookup.info.entry_id)} @click=${this.#_}>
          ${l(this.hass,"card_settings")}
        </a>
      </footer>
    `:c}#_=t=>{!t.ctrlKey&&!t.metaKey&&!t.shiftKey&&this.close()}};var Ue="data-held",mt=class{#t;#e;#n=!1;#o;#i;#r=!1;#d=!1;#s;#a=t=>this.#l(t);constructor(t,e){this.#t=t,this.#e=e,t.addController(this)}hostDisconnected(){this.#n=!1,this.#d=!1,this.#p(),this.#c()}cancelPress(){this.#c()}binding(){return{click:t=>{if(this.#d){this.#d=!1,t.preventDefault(),t.stopPropagation();return}this.#u()},keydown:t=>{t.key==="Enter"?(t.preventDefault(),t.repeat||this.#e().tap()):t.key===" "&&(t.preventDefault(),this.#n=!0)},keyup:t=>{if(t.key!==" ")return;let e=this.#n;this.#n=!1,e&&this.#e().tap()},pointerdown:t=>this.#h(t),pointerup:t=>{if(t.pointerId!==this.#o)return;let e=this.#r;this.#c();let{hold:o}=this.#e();e&&o!==void 0&&(this.#d=!0,o())},pointercancel:t=>this.#l(t),pointerleave:t=>this.#l(t),contextmenu:t=>{this.#o!==void 0&&t.preventDefault()}}}#u(){let{tap:t,doubleTap:e}=this.#e(),o=this.#s!==void 0;this.#p(),e===void 0?t():o?e():this.#s=setTimeout(()=>{this.#s=void 0,this.#e().tap()},250)}#p(){clearTimeout(this.#s),this.#s=void 0}#h(t){this.#e().hold===void 0||!t.isPrimary||t.button!==0||(this.#d=!1,this.#c(),this.#o=t.pointerId,window.addEventListener("pointerup",this.#a),window.addEventListener("pointercancel",this.#a),this.#i=setTimeout(()=>{this.#i=void 0,this.#r=!0,this.#t.setAttribute(Ue,"")},500))}#l(t){t.pointerId===this.#o&&this.#c()}#c(){clearTimeout(this.#i),this.#i=void 0,this.#o=void 0,this.#r=!1,window.removeEventListener("pointerup",this.#a),window.removeEventListener("pointercancel",this.#a),this.#t.removeAttribute(Ue)}};var D=80,Ie=6,Ut=(D-Ie)/2,De=2*Math.PI*Ut;function Tn(n){if(n.state!=="counting")return u`<span class="icon">${ct(n)}</span>`;let t=M(n.remaining);return u`<span class="time" aria-hidden="true">${t}</span>`}function ze(n,t,e,o,i,r){let s=D/2,d=U(t);return u`
    <ha-card class="round ${n.state} ${t.show_turn_off?"with-turn-off":""}">
      <div
        class="body"
        role=${$(d?"button":void 0)}
        tabindex=${$(d?"0":void 0)}
        aria-haspopup=${$(lt(t))}
        aria-labelledby=${$(d?"label":void 0)}
        @click=${o.click}
        @keydown=${o.keydown}
        @keyup=${o.keyup}
        @pointerdown=${o.pointerdown}
        @pointerup=${o.pointerup}
        @pointercancel=${o.pointercancel}
        @pointerleave=${o.pointerleave}
        @contextmenu=${o.contextmenu}
      ></div>
      <div class="content">
        <div class="dial">
          <svg class="ring" viewBox="0 0 ${D} ${D}" aria-hidden="true">
            <circle class="track" cx=${s} cy=${s} r=${Ut}></circle>
            <circle
              class="progress"
              cx=${s}
              cy=${s}
              r=${Ut}
              transform="rotate(-90 ${s} ${s})"
              stroke-dasharray=${De}
              stroke-dashoffset=${(1-n.progress)*De}
            ></circle>
          </svg>
          <span class="centre">
            ${Tn(n)}
          </span>
        </div>
        <span class="text" id="label">
          <span class="name">${n.name}</span>
          <span class="status">${pt(n,t,e,r)}</span>
        </span>
        ${t.show_turn_off?u`<div class="turn-off-slot">${ut(n,t,e,i)}</div>`:c}
      </div>
    </ha-card>
  `}var je=_`
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
    stroke-width: ${Ie};
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
    height: 40px;
    margin-top: 4px;
  }
  @container (width < ${Z.round}px) {
    ${J(_`.round`)}
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
`;var Dt="timerify-card",Q={pill:{columns:6,rows:1,min_columns:3,min_rows:1,max_rows:1},round:{columns:3,rows:2,min_columns:2,min_rows:2,max_rows:3},pillWithTurnOff:{columns:6,rows:1,min_columns:6,min_rows:1,max_rows:1},pillWithTurnOffAndChip:{columns:9,rows:1,min_columns:9,min_rows:1,max_rows:1},roundWithTurnOff:{columns:3,rows:3,min_columns:3,min_rows:3,max_rows:3}},It=class extends b{static properties={hass:{attribute:!1,noAccessor:!0},_config:{state:!0},_lookup:{state:!0}};static styles=[Pe,Ne,je,_`
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
    `];static getConfigForm=Ce;static getStubConfig=Ee;#t;#e=new Set;#n=!1;#o=!1;#i=new mt(this,()=>this.#_());#r=this.#i.binding();#d=()=>{let{_config:t,hass:e}=this;t?.chip!==void 0&&e!==void 0&&K(e,t.entity,t.chip)};#s=()=>{let{_config:t,hass:e}=this;t!==void 0&&e!==void 0&&O(e,t.entity)};#a;#u=!1;constructor(){super(),this._lookup={status:"pending"},new rt(this,()=>this.#a?.endsAt,()=>X(this._lookup))}get hass(){return this.#t}set hass(t){let e=this.#t;this.#t=t,this.requestUpdate("hass",e),this.#p(e,t)}setConfig(t){let e=be(t),o=this._config?.entity!==e.entity;this._config=e,o&&(this._lookup={status:"pending"},this.#l())}getCardSize(){return this._config?.layout!=="round"?1:this._config.show_turn_off?4:3}getGridOptions(){let t=this._config;return t?.layout==="round"?t.show_turn_off?Q.roundWithTurnOff:Q.round:t?.show_turn_off?t.chip===void 0?Q.pillWithTurnOff:Q.pillWithTurnOffAndChip:Q.pill}async getUpdateComplete(){let t=await super.getUpdateComplete();for(;this.#e.size>0;)await Promise.allSettled([...this.#e]),t=await super.getUpdateComplete();return t}#p(t,e){let o=t!==void 0&&e.connected&&!t.connected;(t===void 0||t.language!==e.language||o)&&this.#h(it(e));let i=this._config?.entity;i!==void 0&&(t===void 0||t.entities!==e.entities||o||L(e.states[i])&&!L(t.states[i]))&&this.#l()}#h(t){let e=t.finally(()=>this.#e.delete(e));this.#e.add(e)}#l(){if(this.#n){this.#o=!0;return}this.#n=!0,this.#h(this.#c())}async#c(){try{do{this.#o=!1;let t=this._config?.entity;if(this.#t===void 0||t===void 0)return;let e=await ke(this.#t,t);this.#o||(this._lookup=e)}while(this.#o)}finally{this.#n=!1}}willUpdate(){this.#u=this.shadowRoot?.activeElement?.classList.contains("turn-off")===!0}updated(){this.#u&&this.shadowRoot?.querySelector(".turn-off")===null&&this.#f()}#f(){let t=this._config;t!==void 0&&U(t)&&this.renderRoot.querySelector(".body")?.focus()}shouldUpdate(t){let e=this._lookup.status==="found"?this._lookup.info:void 0,o=this._config?at(this._config.entity,e):[];return dt(t,this.#t,o)}get#m(){return this.renderRoot.querySelector("timerify-card-popup")}#_(){let t=this._config,e={tap:()=>this.#g("tap")};return t!==void 0&&t.double_tap!=="none"&&(e.doubleTap=()=>this.#g("double_tap")),t!==void 0&&t.hold!=="none"&&(e.hold=()=>this.#g("hold")),e}#g(t){let{_config:e,hass:o}=this;if(!(e===void 0||o===void 0))switch(e[t]){case"popup":this.#i.cancelPress(),this.#m?.open();break;case"run":Tt(o,e.entity);break;case"stop":O(o,e.entity);break;case"run_or_stop":this.#y(o,e);break;case"action":this.#b(t,e);break;case"none":break}}#y(t,e){let o=this.#a;o!==void 0&&(N(o)?O(t,e.entity):o.state==="idle"&&Tt(t,e.entity))}#b(t,e){if(this._lookup.status!=="found")return;let o=Object.fromEntries(Mt.filter(i=>e[i]!==void 0).map(i=>[i,e[i]]));this.dispatchEvent(new CustomEvent("hass-action",{detail:{config:{entity:this._lookup.info.target,...o},action:t},bubbles:!0,composed:!0}))}#v(t,e){let o=this._lookup;if(o.status==="unauthorized")return l(t,"card_not_allowed",{entity:e.entity});if(o.status==="incomplete")return l(t,"card_timer_incomplete",{entity:e.entity});if(o.status==="found"&&st(o.info,o.info.ends_at))return l(t,"card_ends_at_disabled",{sensor:o.info.ends_at});if(o.status!=="not_found")return;let i=t.states[e.entity];return i===void 0?l(t,"card_entity_not_found",{entity:e.entity}):L(i)?l(t,"card_not_a_timer",{entity:e.entity}):void 0}render(){let t=this.#t,e=this._config;if(!t||!e)return c;let o=this.#v(t,e);if(o)return this.#a=void 0,u`
        <ha-card>
          <div class="warning" role="alert">
            <ha-icon icon="mdi:alert-outline"></ha-icon>
            <span>${o}</span>
          </div>
        </ha-card>
      `;let i=X(this._lookup),r=Te(t,e,this._lookup,i);return this.#a=r,u`
      ${e.layout==="round"?ze(r,e,t,this.#r,this.#s,i):Le(r,e,t,this.#r,this.#d,this.#s,i)}
      ${this._lookup.status==="found"?u`
            <timerify-card-popup
              .hass=${t}
              .config=${e}
              .lookup=${this._lookup}
              .view=${r}
              @closed=${()=>this.#f()}
            ></timerify-card-popup>
          `:c}
    `}};if(!customElements.get(Dt)){customElements.define("timerify-card-popup",ft),customElements.define(Dt,It);let n={type:Dt,name:"Timerify",description:l(void 0,"card_picker_description"),preview:!0,documentationURL:"https://github.com/klimofey/timerify#dashboard-card"};(window.customCards??=[]).push(n),he(()=>{n.description=l(A(),"card_picker_description")})}export{It as TimerifyCard};
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
