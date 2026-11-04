var dt=globalThis,ct=dt.ShadowRoot&&(dt.ShadyCSS===void 0||dt.ShadyCSS.nativeShadow)&&"adoptedStyleSheets"in Document.prototype&&"replace"in CSSStyleSheet.prototype,Ct=Symbol(),Jt=new WeakMap,V=class{constructor(t,e,o){if(this._$cssResult$=!0,o!==Ct)throw Error("CSSResult is not constructable. Use `unsafeCSS` or `css` instead.");this.cssText=t,this.t=e}get styleSheet(){let t=this.o,e=this.t;if(ct&&t===void 0){let o=e!==void 0&&e.length===1;o&&(t=Jt.get(e)),t===void 0&&((this.o=t=new CSSStyleSheet).replaceSync(this.cssText),o&&Jt.set(e,t))}return t}toString(){return this.cssText}},lt=n=>new V(typeof n=="string"?n:n+"",void 0,Ct),y=(n,...t)=>{let e=n.length===1?n[0]:t.reduce((o,i,r)=>o+(s=>{if(s._$cssResult$===!0)return s.cssText;if(typeof s=="number")return s;throw Error("Value passed to 'css' function must be a 'css' function result: "+s+". Use 'unsafeCSS' to pass non-literal values, but take care to ensure page security.")})(i)+n[r+1],n[0]);return new V(e,n,Ct)},Qt=(n,t)=>{if(ct)n.adoptedStyleSheets=t.map(e=>e instanceof CSSStyleSheet?e:e.styleSheet);else for(let e of t){let o=document.createElement("style"),i=dt.litNonce;i!==void 0&&o.setAttribute("nonce",i),o.textContent=e.cssText,n.appendChild(o)}},Et=ct?n=>n:n=>n instanceof CSSStyleSheet?(t=>{let e="";for(let o of t.cssRules)e+=o.cssText;return lt(e)})(n):n;var{is:on,defineProperty:rn,getOwnPropertyDescriptor:sn,getOwnPropertyNames:an,getOwnPropertySymbols:dn,getPrototypeOf:cn}=Object,ut=globalThis,te=ut.trustedTypes,ln=te?te.emptyScript:"",un=ut.reactiveElementPolyfillSupport,W=(n,t)=>n,kt={toAttribute(n,t){switch(t){case Boolean:n=n?ln:null;break;case Object:case Array:n=n==null?n:JSON.stringify(n)}return n},fromAttribute(n,t){let e=n;switch(t){case Boolean:e=n!==null;break;case Number:e=n===null?null:Number(n);break;case Object:case Array:try{e=JSON.parse(n)}catch{e=null}}return e}},ne=(n,t)=>!on(n,t),ee={attribute:!0,type:String,converter:kt,reflect:!1,useDefault:!1,hasChanged:ne};Symbol.metadata??=Symbol("metadata"),ut.litPropertyMetadata??=new WeakMap;var A=class extends HTMLElement{static addInitializer(t){this._$Ei(),(this.l??=[]).push(t)}static get observedAttributes(){return this.finalize(),this._$Eh&&[...this._$Eh.keys()]}static createProperty(t,e=ee){if(e.state&&(e.attribute=!1),this._$Ei(),this.prototype.hasOwnProperty(t)&&((e=Object.create(e)).wrapped=!0),this.elementProperties.set(t,e),!e.noAccessor){let o=Symbol(),i=this.getPropertyDescriptor(t,o,e);i!==void 0&&rn(this.prototype,t,i)}}static getPropertyDescriptor(t,e,o){let{get:i,set:r}=sn(this.prototype,t)??{get(){return this[e]},set(s){this[e]=s}};return{get:i,set(s){let c=i?.call(this);r?.call(this,s),this.requestUpdate(t,c,o)},configurable:!0,enumerable:!0}}static getPropertyOptions(t){return this.elementProperties.get(t)??ee}static _$Ei(){if(this.hasOwnProperty(W("elementProperties")))return;let t=cn(this);t.finalize(),t.l!==void 0&&(this.l=[...t.l]),this.elementProperties=new Map(t.elementProperties)}static finalize(){if(this.hasOwnProperty(W("finalized")))return;if(this.finalized=!0,this._$Ei(),this.hasOwnProperty(W("properties"))){let e=this.properties,o=[...an(e),...dn(e)];for(let i of o)this.createProperty(i,e[i])}let t=this[Symbol.metadata];if(t!==null){let e=litPropertyMetadata.get(t);if(e!==void 0)for(let[o,i]of e)this.elementProperties.set(o,i)}this._$Eh=new Map;for(let[e,o]of this.elementProperties){let i=this._$Eu(e,o);i!==void 0&&this._$Eh.set(i,e)}this.elementStyles=this.finalizeStyles(this.styles)}static finalizeStyles(t){let e=[];if(Array.isArray(t)){let o=new Set(t.flat(1/0).reverse());for(let i of o)e.unshift(Et(i))}else t!==void 0&&e.push(Et(t));return e}static _$Eu(t,e){let o=e.attribute;return o===!1?void 0:typeof o=="string"?o:typeof t=="string"?t.toLowerCase():void 0}constructor(){super(),this._$Ep=void 0,this.isUpdatePending=!1,this.hasUpdated=!1,this._$Em=null,this._$Ev()}_$Ev(){this._$ES=new Promise(t=>this.enableUpdating=t),this._$AL=new Map,this._$E_(),this.requestUpdate(),this.constructor.l?.forEach(t=>t(this))}addController(t){(this._$EO??=new Set).add(t),this.renderRoot!==void 0&&this.isConnected&&t.hostConnected?.()}removeController(t){this._$EO?.delete(t)}_$E_(){let t=new Map,e=this.constructor.elementProperties;for(let o of e.keys())this.hasOwnProperty(o)&&(t.set(o,this[o]),delete this[o]);t.size>0&&(this._$Ep=t)}createRenderRoot(){let t=this.shadowRoot??this.attachShadow(this.constructor.shadowRootOptions);return Qt(t,this.constructor.elementStyles),t}connectedCallback(){this.renderRoot??=this.createRenderRoot(),this.enableUpdating(!0),this._$EO?.forEach(t=>t.hostConnected?.())}enableUpdating(t){}disconnectedCallback(){this._$EO?.forEach(t=>t.hostDisconnected?.())}attributeChangedCallback(t,e,o){this._$AK(t,o)}_$ET(t,e){let o=this.constructor.elementProperties.get(t),i=this.constructor._$Eu(t,o);if(i!==void 0&&o.reflect===!0){let r=(o.converter?.toAttribute!==void 0?o.converter:kt).toAttribute(e,o.type);this._$Em=t,r==null?this.removeAttribute(i):this.setAttribute(i,r),this._$Em=null}}_$AK(t,e){let o=this.constructor,i=o._$Eh.get(t);if(i!==void 0&&this._$Em!==i){let r=o.getPropertyOptions(i),s=typeof r.converter=="function"?{fromAttribute:r.converter}:r.converter?.fromAttribute!==void 0?r.converter:kt;this._$Em=i;let c=s.fromAttribute(e,r.type);this[i]=c??this._$Ej?.get(i)??c,this._$Em=null}}requestUpdate(t,e,o,i=!1,r){if(t!==void 0){let s=this.constructor;if(i===!1&&(r=this[t]),o??=s.getPropertyOptions(t),!((o.hasChanged??ne)(r,e)||o.useDefault&&o.reflect&&r===this._$Ej?.get(t)&&!this.hasAttribute(s._$Eu(t,o))))return;this.C(t,e,o)}this.isUpdatePending===!1&&(this._$ES=this._$EP())}C(t,e,{useDefault:o,reflect:i,wrapped:r},s){o&&!(this._$Ej??=new Map).has(t)&&(this._$Ej.set(t,s??e??this[t]),r!==!0||s!==void 0)||(this._$AL.has(t)||(this.hasUpdated||o||(e=void 0),this._$AL.set(t,e)),i===!0&&this._$Em!==t&&(this._$Eq??=new Set).add(t))}async _$EP(){this.isUpdatePending=!0;try{await this._$ES}catch(e){Promise.reject(e)}let t=this.scheduleUpdate();return t!=null&&await t,!this.isUpdatePending}scheduleUpdate(){return this.performUpdate()}performUpdate(){if(!this.isUpdatePending)return;if(!this.hasUpdated){if(this.renderRoot??=this.createRenderRoot(),this._$Ep){for(let[i,r]of this._$Ep)this[i]=r;this._$Ep=void 0}let o=this.constructor.elementProperties;if(o.size>0)for(let[i,r]of o){let{wrapped:s}=r,c=this[i];s!==!0||this._$AL.has(i)||c===void 0||this.C(i,void 0,r,c)}}let t=!1,e=this._$AL;try{t=this.shouldUpdate(e),t?(this.willUpdate(e),this._$EO?.forEach(o=>o.hostUpdate?.()),this.update(e)):this._$EM()}catch(o){throw t=!1,this._$EM(),o}t&&this._$AE(e)}willUpdate(t){}_$AE(t){this._$EO?.forEach(e=>e.hostUpdated?.()),this.hasUpdated||(this.hasUpdated=!0,this.firstUpdated(t)),this.updated(t)}_$EM(){this._$AL=new Map,this.isUpdatePending=!1}get updateComplete(){return this.getUpdateComplete()}getUpdateComplete(){return this._$ES}shouldUpdate(t){return!0}update(t){this._$Eq&&=this._$Eq.forEach(e=>this._$ET(e,this[e])),this._$EM()}updated(t){}firstUpdated(t){}};A.elementStyles=[],A.shadowRootOptions={mode:"open"},A[W("elementProperties")]=new Map,A[W("finalized")]=new Map,un?.({ReactiveElement:A}),(ut.reactiveElementVersions??=[]).push("2.1.2");var zt=globalThis,oe=n=>n,ht=zt.trustedTypes,ie=ht?ht.createPolicy("lit-html",{createHTML:n=>n}):void 0,le="$lit$",C=`lit$${Math.random().toFixed(9).slice(2)}$`,ue="?"+C,hn=`<${ue}>`,R=document,q=()=>R.createComment(""),Z=n=>n===null||typeof n!="object"&&typeof n!="function",Lt=Array.isArray,pn=n=>Lt(n)||typeof n?.[Symbol.iterator]=="function",Tt=`[ 	
\f\r]`,K=/<(?:(!--|\/[^a-zA-Z])|(\/?[a-zA-Z][^>\s]*)|(\/?$))/g,re=/-->/g,se=/>/g,T=RegExp(`>|${Tt}(?:([^\\s"'>=/]+)(${Tt}*=${Tt}*(?:[^ 	
\f\r"'\`<>=]|("|')|))|$)`,"g"),ae=/'/g,de=/"/g,he=/^(?:script|style|textarea|title)$/i,Dt=n=>(t,...e)=>({_$litType$:n,strings:t,values:e}),h=Dt(1),io=Dt(2),ro=Dt(3),S=Symbol.for("lit-noChange"),u=Symbol.for("lit-nothing"),ce=new WeakMap,P=R.createTreeWalker(R,129);function pe(n,t){if(!Lt(n)||!n.hasOwnProperty("raw"))throw Error("invalid template strings array");return ie!==void 0?ie.createHTML(t):t}var mn=(n,t)=>{let e=n.length-1,o=[],i,r=t===2?"<svg>":t===3?"<math>":"",s=K;for(let c=0;c<e;c++){let d=n[c],p,f,m=-1,b=0;for(;b<d.length&&(s.lastIndex=b,f=s.exec(d),f!==null);)b=s.lastIndex,s===K?f[1]==="!--"?s=re:f[1]!==void 0?s=se:f[2]!==void 0?(he.test(f[2])&&(i=RegExp("</"+f[2],"g")),s=T):f[3]!==void 0&&(s=T):s===T?f[0]===">"?(s=i??K,m=-1):f[1]===void 0?m=-2:(m=s.lastIndex-f[2].length,p=f[1],s=f[3]===void 0?T:f[3]==='"'?de:ae):s===de||s===ae?s=T:s===re||s===se?s=K:(s=T,i=void 0);let v=s===T&&n[c+1].startsWith("/>")?" ":"";r+=s===K?d+hn:m>=0?(o.push(p),d.slice(0,m)+le+d.slice(m)+C+v):d+C+(m===-2?c:v)}return[pe(n,r+(n[e]||"<?>")+(t===2?"</svg>":t===3?"</math>":"")),o]},G=class n{constructor({strings:t,_$litType$:e},o){let i;this.parts=[];let r=0,s=0,c=t.length-1,d=this.parts,[p,f]=mn(t,e);if(this.el=n.createElement(p,o),P.currentNode=this.el.content,e===2||e===3){let m=this.el.content.firstChild;m.replaceWith(...m.childNodes)}for(;(i=P.nextNode())!==null&&d.length<c;){if(i.nodeType===1){if(i.hasAttributes())for(let m of i.getAttributeNames())if(m.endsWith(le)){let b=f[s++],v=i.getAttribute(m).split(C),k=/([.?@])?(.*)/.exec(b);d.push({type:1,index:r,name:k[2],strings:v,ctor:k[1]==="."?Rt:k[1]==="?"?Ht:k[1]==="@"?Ot:L}),i.removeAttribute(m)}else m.startsWith(C)&&(d.push({type:6,index:r}),i.removeAttribute(m));if(he.test(i.tagName)){let m=i.textContent.split(C),b=m.length-1;if(b>0){i.textContent=ht?ht.emptyScript:"";for(let v=0;v<b;v++)i.append(m[v],q()),P.nextNode(),d.push({type:2,index:++r});i.append(m[b],q())}}}else if(i.nodeType===8)if(i.data===ue)d.push({type:2,index:r});else{let m=-1;for(;(m=i.data.indexOf(C,m+1))!==-1;)d.push({type:7,index:r}),m+=C.length-1}r++}}static createElement(t,e){let o=R.createElement("template");return o.innerHTML=t,o}};function z(n,t,e=n,o){if(t===S)return t;let i=o!==void 0?e._$Co?.[o]:e._$Cl,r=Z(t)?void 0:t._$litDirective$;return i?.constructor!==r&&(i?._$AO?.(!1),r===void 0?i=void 0:(i=new r(n),i._$AT(n,e,o)),o!==void 0?(e._$Co??=[])[o]=i:e._$Cl=i),i!==void 0&&(t=z(n,i._$AS(n,t.values),i,o)),t}var Pt=class{constructor(t,e){this._$AV=[],this._$AN=void 0,this._$AD=t,this._$AM=e}get parentNode(){return this._$AM.parentNode}get _$AU(){return this._$AM._$AU}u(t){let{el:{content:e},parts:o}=this._$AD,i=(t?.creationScope??R).importNode(e,!0);P.currentNode=i;let r=P.nextNode(),s=0,c=0,d=o[0];for(;d!==void 0;){if(s===d.index){let p;d.type===2?p=new Y(r,r.nextSibling,this,t):d.type===1?p=new d.ctor(r,d.name,d.strings,this,t):d.type===6&&(p=new Mt(r,this,t)),this._$AV.push(p),d=o[++c]}s!==d?.index&&(r=P.nextNode(),s++)}return P.currentNode=R,i}p(t){let e=0;for(let o of this._$AV)o!==void 0&&(o.strings!==void 0?(o._$AI(t,o,e),e+=o.strings.length-2):o._$AI(t[e])),e++}},Y=class n{get _$AU(){return this._$AM?._$AU??this._$Cv}constructor(t,e,o,i){this.type=2,this._$AH=u,this._$AN=void 0,this._$AA=t,this._$AB=e,this._$AM=o,this.options=i,this._$Cv=i?.isConnected??!0}get parentNode(){let t=this._$AA.parentNode,e=this._$AM;return e!==void 0&&t?.nodeType===11&&(t=e.parentNode),t}get startNode(){return this._$AA}get endNode(){return this._$AB}_$AI(t,e=this){t=z(this,t,e),Z(t)?t===u||t==null||t===""?(this._$AH!==u&&this._$AR(),this._$AH=u):t!==this._$AH&&t!==S&&this._(t):t._$litType$!==void 0?this.$(t):t.nodeType!==void 0?this.T(t):pn(t)?this.k(t):this._(t)}O(t){return this._$AA.parentNode.insertBefore(t,this._$AB)}T(t){this._$AH!==t&&(this._$AR(),this._$AH=this.O(t))}_(t){this._$AH!==u&&Z(this._$AH)?this._$AA.nextSibling.data=t:this.T(R.createTextNode(t)),this._$AH=t}$(t){let{values:e,_$litType$:o}=t,i=typeof o=="number"?this._$AC(t):(o.el===void 0&&(o.el=G.createElement(pe(o.h,o.h[0]),this.options)),o);if(this._$AH?._$AD===i)this._$AH.p(e);else{let r=new Pt(i,this),s=r.u(this.options);r.p(e),this.T(s),this._$AH=r}}_$AC(t){let e=ce.get(t.strings);return e===void 0&&ce.set(t.strings,e=new G(t)),e}k(t){Lt(this._$AH)||(this._$AH=[],this._$AR());let e=this._$AH,o,i=0;for(let r of t)i===e.length?e.push(o=new n(this.O(q()),this.O(q()),this,this.options)):o=e[i],o._$AI(r),i++;i<e.length&&(this._$AR(o&&o._$AB.nextSibling,i),e.length=i)}_$AR(t=this._$AA.nextSibling,e){for(this._$AP?.(!1,!0,e);t!==this._$AB;){let o=oe(t).nextSibling;oe(t).remove(),t=o}}setConnected(t){this._$AM===void 0&&(this._$Cv=t,this._$AP?.(t))}},L=class{get tagName(){return this.element.tagName}get _$AU(){return this._$AM._$AU}constructor(t,e,o,i,r){this.type=1,this._$AH=u,this._$AN=void 0,this.element=t,this.name=e,this._$AM=i,this.options=r,o.length>2||o[0]!==""||o[1]!==""?(this._$AH=Array(o.length-1).fill(new String),this.strings=o):this._$AH=u}_$AI(t,e=this,o,i){let r=this.strings,s=!1;if(r===void 0)t=z(this,t,e,0),s=!Z(t)||t!==this._$AH&&t!==S,s&&(this._$AH=t);else{let c=t,d,p;for(t=r[0],d=0;d<r.length-1;d++)p=z(this,c[o+d],e,d),p===S&&(p=this._$AH[d]),s||=!Z(p)||p!==this._$AH[d],p===u?t=u:t!==u&&(t+=(p??"")+r[d+1]),this._$AH[d]=p}s&&!i&&this.j(t)}j(t){t===u?this.element.removeAttribute(this.name):this.element.setAttribute(this.name,t??"")}},Rt=class extends L{constructor(){super(...arguments),this.type=3}j(t){this.element[this.name]=t===u?void 0:t}},Ht=class extends L{constructor(){super(...arguments),this.type=4}j(t){this.element.toggleAttribute(this.name,!!t&&t!==u)}},Ot=class extends L{constructor(t,e,o,i,r){super(t,e,o,i,r),this.type=5}_$AI(t,e=this){if((t=z(this,t,e,0)??u)===S)return;let o=this._$AH,i=t===u&&o!==u||t.capture!==o.capture||t.once!==o.once||t.passive!==o.passive,r=t!==u&&(o===u||i);i&&this.element.removeEventListener(this.name,this,o),r&&this.element.addEventListener(this.name,this,t),this._$AH=t}handleEvent(t){typeof this._$AH=="function"?this._$AH.call(this.options?.host??this.element,t):this._$AH.handleEvent(t)}},Mt=class{constructor(t,e,o){this.element=t,this.type=6,this._$AN=void 0,this._$AM=e,this.options=o}get _$AU(){return this._$AM._$AU}_$AI(t){z(this,t)}};var fn=zt.litHtmlPolyfillSupport;fn?.(G,Y),(zt.litHtmlVersions??=[]).push("3.3.3");var me=(n,t,e)=>{let o=e?.renderBefore??t,i=o._$litPart$;if(i===void 0){let r=e?.renderBefore??null;o._$litPart$=i=new Y(t.insertBefore(q(),r),r,void 0,e??{})}return i._$AI(n),i};var It=globalThis,w=class extends A{constructor(){super(...arguments),this.renderOptions={host:this},this._$Do=void 0}createRenderRoot(){let t=super.createRenderRoot();return this.renderOptions.renderBefore??=t.firstChild,t}update(t){let e=this.render();this.hasUpdated||(this.renderOptions.isConnected=this.isConnected),super.update(t),this._$Do=me(e,this.renderRoot,this.renderOptions)}connectedCallback(){super.connectedCallback(),this._$Do?.setConnected(!0)}disconnectedCallback(){super.disconnectedCallback(),this._$Do?.setConnected(!1)}render(){return S}};w._$litElement$=!0,w.finalized=!0,It.litElementHydrateSupport?.({LitElement:w});var gn=It.litElementPolyfillSupport;gn?.({LitElement:w});(It.litElementVersions??=[]).push("4.2.2");async function D(n,t,e,o,i){try{await n.callService(t,e,o,{entity_id:i})}catch{}}function fe(n,t,e){return D(n,"number","set_value",{value:e},t)}function X(n,t,e){return D(n,"timerify","add_time",{minutes:e},t)}function Nt(n,t){return D(n,"timerify","run",{},t)}function I(n,t){return D(n,"timerify","stop",{},t)}function ge(n,t,e){return D(n,"switch",e?"turn_on":"turn_off",{},t)}function _e(n,t,e){return D(n,"timerify","cancel_command",{command_id:e},t)}var ye={card_language:"en",card_entity_not_found:"Entity not found: {entity}",card_not_a_timer:"{entity} is not the Run for number of a Timerify timer",card_timer_incomplete:"The timer of {entity} cannot be shown: its target or one of its sensors is missing. Open the timer's page to see why.",card_not_allowed:"You are not allowed to see the timer {entity}",card_ends_at_disabled:"The Ends at sensor of this timer, {sensor}, is disabled. Enable it for the card to work",card_error_entity:"Choose the Run for number of a timer",card_error_layout:"The layout is pill or round",card_error_presets:"Presets are whole minutes from 1 to 1440",card_error_chip:"The quick chip is whole minutes from 1 to 1440",card_error_press:"Tap, double tap and hold can each be popup, run, stop, run_or_stop, action or none",card_error_action:"A Home Assistant action is a set of settings, such as action: more-info",card_error_show_turn_off:"show_turn_off is true or false",card_error_mushroom:"mushroom is true or false",card_close:"Close",card_until:"until {time}",card_until_latest:"by {time} at the latest",card_add_time:"Add {duration}",card_subtract_time:"Take off {duration}",card_presets_above_maximum:"Every preset is longer than this timer's maximum of {maximum}.",card_stop:"Stop",card_turn_off:"Turn off",card_schedule:"Schedule",card_commands:"Pending commands",card_commands_disabled:"Pending commands are hidden: the Next command sensor, {sensor}, is disabled",card_command_on:"On at {time}",card_command_on_for:"On at {time} for {duration}",card_command_off:"Off at {time}",card_cancel_command:"Cancel",card_settings:"Settings",card_picker_description:"The countdown, presets and schedule of a Timerify timer",card_editor_entity:"Timer",card_editor_layout:"Layout",card_editor_layout_pill:"Pill",card_editor_layout_round:"Round",card_editor_name:"Name",card_editor_icon:"Icon",card_editor_presets:"Duration presets (minutes)",card_editor_presets_helper:"Leave empty for {presets}",card_editor_chip:"Quick add chip (minutes, pill only)",card_editor_show_turn_off:"Show a Turn off button",card_editor_mushroom:"Mushroom style",card_editor_mushroom_missing:"Mushroom was not found. The card keeps the Home Assistant look.",card_editor_interactions:"Interactions",card_editor_tap:"Tap behavior",card_editor_double_tap:"Double tap behavior",card_editor_hold:"Hold behavior",card_editor_tap_action:"Tap action",card_editor_double_tap_action:"Double tap action",card_editor_hold_action:"Hold action",card_editor_press_popup:"Open the pop-up",card_editor_press_run:"Run",card_editor_press_stop:"Stop",card_editor_press_run_or_stop:"Start or stop",card_editor_press_action:"Home Assistant action",card_editor_press_none:"Nothing",card_editor_press_helper:"Empty: runs the action below if one is set. Otherwise it does the default.",card_editor_action_helper:'Used when the behavior above is "Home Assistant action" or empty.'};var ve="common",$e="timerify",_n=`component.${$e}.${ve}.`;function Ut(n){return _n+n}function yn(n,t){return n.replace(/\{(\w+)\}/g,(e,o)=>String(t?.[o]??e))}function l(n,t,e){return n?.localize(Ut(t),e)||yn(ye[t],e)}var J,be=Promise.resolve(),we,xe=new Set;function pt(n){return n.language!==J&&(J=n.language,be=bn(n,n.language)),be}async function bn(n,t){let e;try{e=await n.loadBackendTranslation(ve,$e)}catch{J===t&&(J=void 0);return}J===t&&(we={...n,localize:e},xe.forEach(o=>o()))}function H(){return we}function Ae(n){xe.add(n)}var Q=[15,30,45,60,120],Ft=1440,Bt=["popup","run","stop","run_or_stop","action","none"],jt=["tap","double_tap","hold"],Vt=["tap_action","double_tap_action","hold_action"],vn={tap:"tap_action",double_tap:"double_tap_action",hold:"hold_action"},_=class extends Error{constructor(e){super(l(H(),e));this.key=e}key};function Ee(n){let t=typeof n=="number"?n:typeof n=="string"&&/^\d+$/.test(n)?Number(n):void 0;return t!==void 0&&Number.isInteger(t)&&t>=1&&t<=Ft?t:void 0}function $n(n){if(n===void 0||Array.isArray(n)&&n.length===0)return[...Q];if(!Array.isArray(n))throw new _("card_error_presets");let t=new Set;for(let e of n){let o=Ee(e);if(o===void 0)throw new _("card_error_presets");t.add(o)}return[...t]}function wn(n){if(n===void 0)return;let t=Ee(n);if(t===void 0)throw new _("card_error_chip");return t}var ke=n=>typeof n=="object"&&n!==null?n:{},xn=n=>Bt.some(t=>t===n);function An(n){let t=n?.action;return typeof t=="string"&&t!==""?t:void 0}function Sn(n,t,e){let o=An(t);if(n===void 0)return o===void 0?e:o==="none"?"none":"action";if(!xn(n))throw new _("card_error_press");return n==="action"&&o==="none"?"none":n}function Se(n,t){if(n===void 0)return!1;if(typeof n!="boolean")throw new _(t);return n}var Cn=n=>typeof n=="object"&&n!==null&&!Array.isArray(n);function Te(n){let t={};for(let e of Vt){let o=n[e];if(o!==void 0){if(!Cn(o))throw new _("card_error_action");t[e]=o}}return t}var Ce=n=>typeof n=="number"||typeof n=="string";function Pe(n){let t=ke(n),{entity:e,layout:o,presets:i,chip:r}=t;if(e!==void 0&&typeof e!="string")throw new _("card_error_entity");if(o!==void 0&&typeof o!="string")throw new _("card_error_layout");if(i!==void 0&&!(Array.isArray(i)&&i.every(Ce)))throw new _("card_error_presets");if(r!==void 0&&!Ce(r))throw new _("card_error_chip");if(t.show_turn_off!==void 0&&typeof t.show_turn_off!="boolean")throw new _("card_error_show_turn_off");if(t.mushroom!==void 0&&typeof t.mushroom!="boolean")throw new _("card_error_mushroom");for(let s of jt)if(t[s]!==void 0&&typeof t[s]!="string")throw new _("card_error_press");Te(t)}function Re(n){let t=ke(n),{entity:e,layout:o="pill",name:i,icon:r}=t;if(typeof e!="string"||!/^number\.[a-z0-9_]+$/.test(e))throw new _("card_error_entity");if(o!=="pill"&&o!=="round")throw new _("card_error_layout");let s=wn(t.chip),c=Te(t),d=(p,f)=>Sn(t[p],c[vn[p]],f);return{entity:e,layout:o,...typeof i=="string"&&i!==""&&{name:i},...typeof r=="string"&&r!==""&&{icon:r},presets:$n(t.presets),...s!==void 0&&{chip:s},show_turn_off:Se(t.show_turn_off,"card_error_show_turn_off"),mushroom:Se(t.mushroom,"card_error_mushroom"),tap:d("tap","popup"),double_tap:d("double_tap","none"),hold:d("hold",o==="round"?"run_or_stop":"none"),...c}}var mt=class{#t;#e;#n;#i=!1;#r;constructor(t,e,o){this.#t=t,this.#e=e,this.#n=o,t.addController(this)}hostConnected(){this.#i=!0,this.#o()}hostUpdated(){this.#o()}hostDisconnected(){this.#i=!1,this.#o()}#o(){let t=this.#e(),e=this.#i&&t!==void 0&&t.getTime()>this.#n();e&&this.#r===void 0?this.#r=setInterval(()=>this.#t.requestUpdate(),1e3):!e&&this.#r!==void 0&&(clearInterval(this.#r),this.#r=void 0)}};var He=n=>String(n).padStart(2,"0");function N(n){let t=Math.ceil(Math.max(0,n)),e=Math.floor(t/3600),o=Math.floor(t%3600/60),i=He(t%60);return e>0?`${e}:${He(o)}:${i}`:`${o}:${i}`}function En({language:n,time_format:t}){if(t==="12"||t==="24")return t==="12";let e=new Intl.DateTimeFormat(t==="language"?n:void 0,{hour:"numeric"}).resolvedOptions();return e.hourCycle==="h11"||e.hourCycle==="h12"}var tt=1e3,kn=864e5,Tn=49*36e5;function et(n){return n.locale.time_zone==="server"?n.config.time_zone:void 0}function O(n,t){let e=new Intl.DateTimeFormat("en-US",{timeZone:n,year:"numeric",month:"numeric",day:"numeric"}).formatToParts(t),o=i=>Number(e.find(r=>r.type===i)?.value);return Date.UTC(o("year"),o("month")-1,o("day"))/kn}function Oe(n,t){let e=O(n,t),o=Math.floor(t/tt)*tt,i=o+Tn;for(;i-o>tt;){let r=o+Math.floor((i-o)/(2*tt))*tt;O(n,r)>e?i=r:o=r}return i}function nt(n,t,e){let{locale:o}=n,i=et(n),r=O(i,t.getTime())-O(i,e),s=r===0?{}:r>=1&&r<=6?{weekday:"short"}:{month:"short",day:"numeric"};return new Intl.DateTimeFormat(o.language,{...s,hour:"numeric",minute:"2-digit",hourCycle:En(o)?"h12":"h23",timeZone:i}).format(t)}function $(n,t){let e=(s,c)=>new Intl.NumberFormat(n.locale.language,{style:"unit",unit:c,unitDisplay:"short",useGrouping:!1}).format(s),o=Math.floor(t/60),i=t%60,r=o>0?[e(o,"hour")]:[];return(i>0||o===0)&&r.push(e(i,"minute")),r.join(" ")}function Me(n,t,e,o,i){return e.includes(o)&&typeof i=="number"?new Intl.NumberFormat(n.locale.language,{style:"percent",maximumFractionDigits:1}).format(i/100):t===void 0?String(i):o==="hvac_mode"?n.formatEntityState(t,String(i)):n.formatEntityAttributeValue(t,o,i)}var Le="mushroom-entity-card",Pn="data-mushroom",g=(n,t)=>lt(`var(--mush-${n}, ${t})`),a={spacing:g("spacing","10px"),iconSize:g("icon-size","36px"),iconRadius:g("icon-border-radius","50%"),iconSymbolSize:g("icon-symbol-size","0.667em"),primaryColor:g("card-primary-color","var(--primary-text-color)"),primaryFontSize:g("card-primary-font-size","14px"),primaryFontWeight:g("card-primary-font-weight","500"),primaryLineHeight:g("card-primary-line-height","20px"),primaryLetterSpacing:g("card-primary-letter-spacing","0.1px"),secondaryColor:g("card-secondary-color","var(--primary-text-color)"),secondaryFontSize:g("card-secondary-font-size","12px"),secondaryFontWeight:g("card-secondary-font-weight","400"),secondaryLineHeight:g("card-secondary-line-height","16px"),secondaryLetterSpacing:g("card-secondary-letter-spacing","0.4px"),controlHeight:g("control-height","42px"),controlRadius:g("control-border-radius","12px"),controlButtonRatio:g("control-button-ratio","1"),controlIconSize:g("control-icon-size","0.5em"),controlSpacing:g("control-spacing","12px"),chipHeight:g("chip-height","36px"),chipRadius:g("chip-border-radius","19px"),chipPadding:g("chip-padding","0 0.25em"),chipFontSize:g("chip-font-size","0.3em"),chipFontWeight:g("chip-font-weight","bold"),chipBorderWidth:g("chip-border-width","var(--ha-card-border-width, 1px)"),chipBorderColor:g("chip-border-color","var(--ha-card-border-color, var(--divider-color, #e0e0e0))"),chipBoxShadow:g("chip-box-shadow","var(--ha-card-box-shadow, none)"),chipBackground:g("chip-background","var(--ha-card-background, var(--card-background-color, white))"),activeRgb:g("rgb-state-entity","var(--mush-rgb-blue, 33, 150, 243)"),disabledRgb:g("rgb-disabled","var(--rgb-disabled-text-color, 189, 189, 189)")},Wt=()=>customElements.get(Le)!==void 0,ot=new Set,ze=!1;function Rn(n){ot.add(n),!ze&&(ze=!0,customElements.whenDefined(Le).then(()=>{for(let t of ot)t.requestUpdate();ot.clear()}))}var ft=class{#t;#e;constructor(t,e){this.#t=t,this.#e=e,t.addController(this)}hostConnected(){this.#n()}hostUpdate(){this.#n()}hostDisconnected(){ot.delete(this.#t)}#n(){let t=this.#e(),e=Wt();this.#t.toggleAttribute(Pn,t&&e),t&&!e&&this.#t.isConnected?Rn(this.#t):ot.delete(this.#t)}};var De={entity:"card_editor_entity",layout:"card_editor_layout",name:"card_editor_name",icon:"card_editor_icon",presets:"card_editor_presets",chip:"card_editor_chip",show_turn_off:"card_editor_show_turn_off",mushroom:"card_editor_mushroom",interactions:"card_editor_interactions",tap:"card_editor_tap",double_tap:"card_editor_double_tap",hold:"card_editor_hold",tap_action:"card_editor_tap_action",double_tap_action:"card_editor_double_tap_action",hold_action:"card_editor_hold_action"},Hn={popup:"card_editor_press_popup",run:"card_editor_press_run",stop:"card_editor_press_stop",run_or_stop:"card_editor_press_run_or_stop",action:"card_editor_press_action",none:"card_editor_press_none"},On=n=>Object.hasOwn(De,n),Mn=n=>n.endsWith("_action"),zn=n=>jt.some(t=>t===n),Ln={locale:{language:"en"}};function Dn(){return H()??Ln}function In(n){return l({localize:n},"card_language")}function Nn(n){let t=In(n);return new Intl.ListFormat(t,{style:"long",type:"conjunction"}).format(Q.map(e=>$({locale:{language:t}},e)))}async function Ie(){let n=H(),t=Bt.map(e=>({value:e,label:l(n,Hn[e])}));return{schema:[{name:"entity",required:!0,selector:{entity:{filter:{integration:"timerify",domain:"number"}}}},{name:"layout",selector:{select:{options:[{value:"pill",label:l(n,"card_editor_layout_pill")},{value:"round",label:l(n,"card_editor_layout_round")}]}}},{name:"",type:"grid",schema:[{name:"name",selector:{text:{}}},{name:"icon",selector:{icon:{}}}]},{name:"presets",selector:{select:{multiple:!0,custom_value:!0,options:Q.map(e=>({value:String(e),label:$(Dn(),e)}))}}},{name:"chip",selector:{number:{min:1,max:Ft,mode:"box"}}},{name:"show_turn_off",selector:{boolean:{}}},{name:"mushroom",selector:{boolean:{}}},{name:"interactions",type:"expandable",flatten:!0,icon:"mdi:gesture-tap",schema:[{name:"tap",selector:{select:{options:t}}},{name:"tap_action",selector:{ui_action:{default_action:"more-info"}}},{name:"double_tap",selector:{select:{options:t}}},{name:"double_tap_action",selector:{ui_action:{default_action:"more-info"}}},{name:"hold",selector:{select:{options:t}}},{name:"hold_action",selector:{ui_action:{default_action:"more-info"}}}]}],assertConfig:Pe,computeLabel:({name:e},o)=>On(e)?o(Ut(De[e])):"",computeHelper:({name:e},o)=>e==="presets"?l({localize:o},"card_editor_presets_helper",{presets:Nn(o)}):e==="mushroom"?Wt()?void 0:l({localize:o},"card_editor_mushroom_missing"):zn(e)?l({localize:o},"card_editor_press_helper"):Mn(e)?l({localize:o},"card_editor_action_helper"):void 0}}function Ne(n,t,e){pt(n);let o=r=>{let s=n.entities[r];return s?.platform==="timerify"&&(s.translation_key==="run_for"||s.translation_key==="run_for_with_target")},i=r=>r.filter(o).sort()[0];return{entity:i(t)??i(e)??i(Object.keys(n.entities))??"",layout:"pill",presets:Q.map(String)}}var Un="not_found",Fn="timer_incomplete",Bn="unauthorized";async function Fe(n,t){let e=Date.now();try{let o=await n.callWS({type:"timerify/timer",entity_id:t}),i=Kt(o.server_time),r=i===void 0?0:i-(e+Date.now())/2;return{status:"found",info:o,clockOffset:r}}catch(o){let i=typeof o=="object"&&o!==null&&"code"in o?o.code:"";return i===Un?{status:"not_found"}:i===Fn?{status:"incomplete"}:{status:i===Bn?"unauthorized":"failed"}}}var M=n=>Date.now()+(n.status==="found"?n.clockOffset:0),gt=(n,t)=>n.disabled_sensors.includes(t),U=n=>n!==void 0&&n.state!=="unavailable"&&n.state!=="unknown";function jn(n,t){return n===void 0||n.state==="unavailable"||n.state==="unknown"?!1:t.states.includes(n.state)===(t.match==="is")}var Vn="mdi:timer-outline",Ue=n=>n===void 0||n.state==="unavailable";function Kt(n){let t=typeof n=="string"?Date.parse(n):Number.NaN;return Number.isNaN(t)?void 0:t}function Be(n,t,e,o){let i=e.status==="found"?e.info:void 0,r=n.states[t.entity],s=i&&n.states[i.target],c=t.name||s&&n.formatEntityName(s,void 0)||r?.attributes.friendly_name||t.entity,d=t.icon?{icon:t.icon}:s?{stateObj:s}:{icon:Vn},p={name:c,icon:d,target:s,remaining:0},f=i&&n.states[i.ends_at];if(i===void 0||f===void 0||Ue(r)||Ue(f))return{...p,state:"unavailable",progress:0};let m=Kt(f.state);if(m===void 0)return jn(s,i.target_on)?{...p,state:"open",progress:1}:{...p,state:"idle",progress:0};if(f.attributes.limit===!0)return{...p,state:"limit",progress:1,endsAt:new Date(m)};let b=Kt(f.attributes.started_at),v=b===void 0?0:(m-b)/1e3,k=Math.max(0,(m-o)/1e3);return{...p,state:"counting",remaining:k,progress:v>0?Math.min(1,k/v):1,endsAt:new Date(m)}}var F=({state:n})=>n==="counting"||n==="limit"||n==="open",it=({state:n})=>n==="counting"||n==="limit";function _t(n,t){return t?[n,t.ends_at,t.next_command,t.target,...t.intervals.map(({entity_id:e})=>e)]:[n]}var Wn=["locale","language","localize","config","user","connected","entities","formatEntityName","formatEntityState","formatEntityAttributeValue"];function yt(n,t,e){for(let i of n.keys())if(i!=="hass")return!0;let o=n.get("hass");return o===void 0||t===void 0?!0:Wn.some(i=>o[i]!==t[i])||e.some(i=>o.states[i]!==t.states[i])}function bt(n){return"stateObj"in n.icon?h`<ha-state-icon .stateObj=${n.icon.stateObj}></ha-state-icon>`:h`<ha-icon .icon=${n.icon.icon}></ha-icon>`}var vt=n=>n.tap==="popup"?"dialog":void 0,B=n=>n.tap!=="none"||n.double_tap!=="none"||n.hold!=="none";function $t(n,t,e,o){if(!t.show_turn_off||!F(n))return u;let i=l(e,"card_turn_off");return h`
    <button class="turn-off" type="button" aria-label=${i} title=${i} @click=${o}>
      <ha-icon class="turn-off-icon" icon="mdi:power"></ha-icon>
      <span class="turn-off-label">${i}</span>
    </button>
  `}var rt={pill:245,pillWithChip:335,round:101},st=n=>y`
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
  :host([data-mushroom]) ${n} .turn-off {
    width: calc(${a.controlHeight} * ${a.controlButtonRatio});
    height: ${a.controlHeight};
    padding: 0;
    border-radius: ${a.controlRadius};
  }
`;function Kn(n,t,e){if(n.state!=="unavailable")return n.target?e.formatEntityState(n.target):"";let o=e.states[t.entity];if(U(o))return"";let i={entity_id:t.entity,state:"unavailable",attributes:{}};return e.formatEntityState(o??i,"unavailable")}function wt(n,t,e,o){if(!it(n)||n.endsAt===void 0)return Kn(n,t,e);let i=nt(e,n.endsAt,o);return n.state==="limit"?h`<span class="until">${l(e,"card_until_latest",{time:i})}</span>`:h`
    <span class="remaining">${N(n.remaining)}</span>
    <span class="until">${l(e,"card_until",{time:i})}</span>
  `}var je=y`
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
    /*
     * A press can reach the body, and a double tap is one of them. Safari zooms the page on a
     * double tap unless the element says otherwise; this leaves it panning and pinch-zoom.
     */
    touch-action: manipulation;
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
  /*
   * The width of the content is what the Turn off button chooses its form by, so the content of
   * a card that has the button is a container, and that of any other card is left as it was.
   */
  .with-turn-off .content {
    container-type: inline-size;
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
  .limit .icon,
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
`,Ve=y`
  :host([data-mushroom]) .icon {
    display: flex;
    flex: none;
    align-items: center;
    justify-content: center;
    width: ${a.iconSize};
    height: ${a.iconSize};
    border-radius: ${a.iconRadius};
    background: rgba(${a.disabledRgb}, 0.2);
    color: rgb(${a.disabledRgb});
    /* The size of the shape is the em of the symbol's size, as in Mushroom. */
    font-size: ${a.iconSize};
    line-height: 0;
    --mdc-icon-size: ${a.iconSymbolSize};
    transition:
      background-color 280ms ease-in-out,
      color 280ms ease-in-out;
  }
  :host([data-mushroom]) .counting .icon,
  :host([data-mushroom]) .limit .icon,
  :host([data-mushroom]) .open .icon {
    background: rgba(${a.activeRgb}, 0.2);
    color: rgb(${a.activeRgb});
  }
  :host([data-mushroom]) .name {
    color: ${a.primaryColor};
    font-size: ${a.primaryFontSize};
    font-weight: ${a.primaryFontWeight};
    line-height: ${a.primaryLineHeight};
    letter-spacing: ${a.primaryLetterSpacing};
  }
  /* Mushroom's chip: a small pill with a border, as high as the theme says. */
  :host([data-mushroom]) .chip {
    display: flex;
    align-items: center;
    justify-content: center;
    box-sizing: border-box;
    height: ${a.chipHeight};
    padding: ${a.chipPadding};
    border: ${a.chipBorderWidth} solid ${a.chipBorderColor};
    border-radius: ${a.chipRadius};
    background: ${a.chipBackground};
    box-shadow: ${a.chipBoxShadow};
    /* The size of the chip is the em of its padding and its text, as in Mushroom. */
    font-size: ${a.chipHeight};
    line-height: 0;
  }
  :host([data-mushroom]) .chip-text {
    font-size: ${a.chipFontSize};
    font-weight: ${a.chipFontWeight};
    line-height: 1;
  }
  /* Mushroom's control: its Turn off button has its height, its radius and its fill. */
  :host([data-mushroom]) .turn-off {
    height: ${a.controlHeight};
    padding: 0 ${a.controlSpacing};
    border-radius: ${a.controlRadius};
    background: rgba(var(--rgb-primary-text-color), 0.05);
  }
  :host([data-mushroom]) .turn-off-icon {
    /* The symbol of the control is the em of its height, as in Mushroom. */
    font-size: ${a.controlHeight};
    --mdc-icon-size: ${a.controlIconSize};
  }
`;var j=class{#t;#e;#n;#i;#r=!1;#o;constructor(t,e,o,i){this.#t=t,this.#e=e,this.#n=o,this.#i=i,t.addController(this)}hostConnected(){this.#r=!0,document.addEventListener("visibilitychange",this.#d),this.#a()}hostUpdated(){this.#a()}hostDisconnected(){this.#r=!1,document.removeEventListener("visibilitychange",this.#d),this.#a()}#d=()=>{document.visibilityState==="visible"&&this.#o!==void 0&&(this.#c(),this.#t.requestUpdate())};#a(){let t=this.#r?this.#s():void 0;if(t===void 0){this.#c();return}let{timeZone:e,midnight:o,delay:i}=t,r=this.#o;if(r!==void 0&&r.timeZone===e&&r.midnight===o)return;this.#c();let s=setTimeout(()=>{this.#o=void 0,this.#t.requestUpdate()},i);this.#o={timer:s,timeZone:e,midnight:o}}#s(){let t=this.#e();if(t.length===0)return;let e=this.#n(),o=this.#i(),i=O(o,e);if(t.every(s=>O(o,s.getTime())===i))return;let r=Oe(o,e);return{timeZone:o,midnight:r,delay:r-e}}#c(){this.#o!==void 0&&(clearTimeout(this.#o.timer),this.#o=void 0)}};var x=n=>n??u;var We={ATTRIBUTE:1,CHILD:2,PROPERTY:3,BOOLEAN_ATTRIBUTE:4,EVENT:5,ELEMENT:6},Ke=n=>(...t)=>({_$litDirective$:n,values:t}),xt=class{constructor(t){}get _$AU(){return this._$AM._$AU}_$AT(t,e,o){this._$Ct=t,this._$AM=e,this._$Ci=o}_$AS(t,e){return this.update(t,e)}update(t,e){return this.render(...e)}};var qe="important",qn=" !"+qe,Ze=Ke(class extends xt{constructor(n){if(super(n),n.type!==We.ATTRIBUTE||n.name!=="style"||n.strings?.length>2)throw Error("The `styleMap` directive must be used in the `style` attribute and must be the only part in the attribute.")}render(n){return Object.keys(n).reduce((t,e)=>{let o=n[e];return o==null?t:t+`${e=e.includes("-")?e:e.replace(/(?:^(webkit|moz|ms|o)|)(?=[A-Z])/g,"-$&").toLowerCase()}:${o};`},"")}update(n,[t]){let{style:e}=n.element;if(this.ft===void 0)return this.ft=new Set(Object.keys(t)),this.render(t);for(let o of this.ft)t[o]==null&&(this.ft.delete(o),o.includes("-")?e.removeProperty(o):e[o]=null);for(let o in t){let i=t[o];if(i!=null){this.ft.add(o);let r=typeof i=="string"&&i.endsWith(qn);o.includes("-")||r?e.setProperty(o,r?i.slice(0,-11):i,r?qe:""):e[o]=i}}return S}});function Ge(n,t,e,o,i,r,s){let c=Math.round(n.progress*1e3)/10,d=B(t);return h`
    <ha-card
      class="pill ${n.state} ${t.chip===void 0?"":"with-chip"} ${t.show_turn_off?"with-turn-off":""}"
    >
      <div
        class="body"
        role=${x(d?"button":void 0)}
        tabindex=${x(d?"0":void 0)}
        aria-haspopup=${x(vt(t))}
        aria-labelledby=${x(d?"label":void 0)}
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
          <span class="fill" style=${Ze({width:`${c}%`})}></span>
        </span>
      </div>
      <div class="content">
        <span class="icon">${bt(n)}</span>
        <span class="text" id="label">
          <span class="name">${n.name}</span>
          <span class="status">${wt(n,t,e,s)}</span>
        </span>
        ${$t(n,t,e,r)}
        ${t.chip===void 0?u:h`
              <button
                class="chip"
                type="button"
                aria-label=${l(e,"card_add_time",{duration:$(e,t.chip)})}
                ?disabled=${n.state==="unavailable"}
                @click=${i}
              >
                <span class="chip-text">+${$(e,t.chip)}</span>
              </button>
            `}
      </div>
    </ha-card>
  `}var Ye=y`
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
  @container (width < ${rt.pill}px) {
    ${st(y`.pill`)}
  }
  @container (width < ${rt.pillWithChip}px) {
    ${st(y`.pill.with-chip`)}
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
  /*
   * The Mushroom style (see mushroomStyles in layout.ts): the card is a card of Home Assistant's
   * own shape, as Mushroom's are, as high as its icon and the spacing around it make it, and
   * never lower than the row of the grid it sits in.
   */
  :host([data-mushroom]) ha-card.pill {
    --timerify-radius: var(--ha-card-border-radius, var(--ha-border-radius-lg, 12px));
    height: max(56px, calc(${a.iconSize} + 2 * ${a.spacing}));
  }
  :host([data-mushroom]) .pill .content {
    gap: ${a.spacing};
    padding: 0 ${a.spacing};
  }
  :host([data-mushroom]) .fill {
    background: rgb(${a.activeRgb});
  }
  :host([data-mushroom]) .pill .status {
    color: ${a.secondaryColor};
    font-size: ${a.secondaryFontSize};
    font-weight: ${a.secondaryFontWeight};
    line-height: ${a.secondaryLineHeight};
    letter-spacing: ${a.secondaryLetterSpacing};
  }
`;function Zn(n){let t=n?.attributes.max;return typeof t=="number"&&Number.isFinite(t)?t:void 0}function Gn(n,t){return t===void 0?[...n]:n.filter(e=>e<=t)}function Xe(n){let t=n?.attributes.commands;return Array.isArray(t)?t.flatMap(e=>{if(typeof e!="object"||e===null)return[];let{id:o,at:i,action:r,minutes:s,settings:c}=e,d=typeof i=="string"?new Date(i):void 0;return typeof o!="string"||d===void 0||Number.isNaN(d.getTime())||r!=="on"&&r!=="off"?[]:[{id:o,at:d,action:r,minutes:typeof s=="number"&&s>0?s:null,settings:typeof c=="object"&&c!==null?Object.entries(c):[]}]}):[]}var Yn=n=>`/config/integrations/integration/timerify#config_entry=${encodeURIComponent(n)}`,At=class extends w{static properties={hass:{attribute:!1},config:{attribute:!1},lookup:{attribute:!1},view:{attribute:!1},opened:{state:!0}};static styles=y`
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
  `;constructor(){super(),this.opened=!1,new j(this,()=>this.opened?[...this.view.state==="limit"&&this.view.endsAt?[this.view.endsAt]:[],...Xe(this.hass.states[this.lookup.info.next_command]).map(({at:t})=>t)]:[],()=>M(this.lookup),()=>et(this.hass))}open(){this.opened=!0}close(){this.#t?.close(),this.#a()}disconnectedCallback(){super.disconnectedCallback(),this.close()}get#t(){return this.renderRoot.querySelector("dialog")}#e=()=>{this.#t?.open||this.#a()};#n=!1;#i=t=>{this.#n=t.target===t.currentTarget};#r=t=>{this.#n&&=t.target===t.currentTarget};#o=()=>{this.#n=!1};#d=t=>{let e=this.#n&&t.target===t.currentTarget;this.#n=!1,e&&this.close()};#a(){this.opened&&(this.opened=!1,this.dispatchEvent(new CustomEvent("closed")))}shouldUpdate(t){if(!this.hasUpdated||t.has("opened"))return!0;let e=_t(this.config.entity,this.lookup.info);return this.opened&&yt(t,this.hass,e)}updated(t){let e=this.#t;t.has("opened")&&this.opened&&e&&!e.open&&e.showModal()}render(){return h`
      <dialog
        aria-labelledby="title"
        @cancel=${()=>this.close()}
        @close=${this.#e}
        @pointerdown=${this.#i}
        @pointerup=${this.#r}
        @pointercancel=${this.#o}
        @click=${this.#d}
      >
        ${this.opened?this.#s():u}
      </dialog>
    `}#s(){let{hass:t,view:e}=this,o=M(this.lookup);return h`
      <div class="wrapper">
        <header>
          <h2 id="title">${e.name}</h2>
          <button class="close" @click=${()=>this.close()}>${l(t,"card_close")}</button>
        </header>
        ${this.#c(o)} ${this.#h()} ${this.#p()} ${this.#l(o)}
        ${this.#f()}
      </div>
    `}#c(t){let{hass:e,view:o}=this;if(!it(o)||o.endsAt===void 0)return u;let i=nt(e,o.endsAt,t);return o.state==="limit"?h`
        <p class="countdown">
          <span class="until">${l(e,"card_until_latest",{time:i})}</span>
        </p>
      `:h`
      <p class="countdown">
        <span class="remaining">${N(o.remaining)}</span>
        <span class="until">${l(e,"card_until",{time:i})}</span>
      </p>
    `}#h(){let{hass:t,config:e,view:o}=this,i=$(t,5),r=it(o),s=F(o),c=o.state==="unavailable",d=Zn(t.states[e.entity]),p=Gn(e.presets,d);return h`
      ${p.length>0?h`
            <div class="presets">
              ${p.map(f=>h`
                  <button
                    class="action preset"
                    ?disabled=${c}
                    @click=${()=>{fe(t,e.entity,f)}}
                  >
                    ${$(t,f)}
                  </button>
                `)}
            </div>
          `:d===void 0?u:h`
              <p class="note above-maximum">
                ${l(t,"card_presets_above_maximum",{maximum:$(t,d)})}
              </p>
            `}
      <div class="adjust">
        <button
          class="action step"
          aria-label=${l(t,"card_subtract_time",{duration:i})}
          ?disabled=${!r}
          @click=${()=>{X(t,e.entity,-5)}}
        >
          −${i}
        </button>
        <button
          class="action step"
          aria-label=${l(t,"card_add_time",{duration:i})}
          ?disabled=${c}
          @click=${()=>{X(t,e.entity,5)}}
        >
          +${i}
        </button>
        <button
          class="action stop"
          ?disabled=${!s}
          @click=${()=>{I(t,e.entity)}}
        >
          ${l(t,"card_stop")}
        </button>
      </div>
    `}#p(){let{intervals:t}=this.lookup.info;return t.length===0?u:h`
      <section class="schedule">
        <h3>${l(this.hass,"card_schedule")}</h3>
        <ul>
          ${t.map(e=>h`<li>${this.#u(e)}</li>`)}
        </ul>
      </section>
    `}#u({entity_id:t,title:e}){let{hass:o}=this,i=o.states[t],r=i!==void 0&&i.state!=="unavailable",s=r&&i.state==="on",c=i??{entity_id:t,state:"unavailable",attributes:{}};return h`
      <button
        class="interval"
        role="switch"
        aria-checked=${s?"true":"false"}
        ?disabled=${!r}
        @click=${()=>{ge(o,t,!s)}}
      >
        <span class="label">
          <span class="title">${e}</span>
          ${r?u:h`<span class="state">${o.formatEntityState(c,"unavailable")}</span>`}
        </span>
        <span class="track" aria-hidden="true"><span class="knob"></span></span>
      </button>
    `}#l(t){let{hass:e,config:o,view:i}=this,{info:r}=this.lookup;if(gt(r,r.next_command))return h`
        <section class="commands">
          <p class="note">${l(e,"card_commands_disabled",{sensor:r.next_command})}</p>
        </section>
      `;let s=Xe(e.states[r.next_command]);if(s.length===0)return u;let c=i.state==="unavailable";return h`
      <section class="commands">
        <h3>${l(e,"card_commands")}</h3>
        <ul>
          ${s.map((d,p)=>{let f=d.settings.map(([m,b])=>Me(e,i.target,r.percent_settings,m,b));return h`
              <li>
                <div class="command" id="command-${p}">
                  <span class="what">${this.#m(d,t)}</span>
                  ${f.length===0?u:h`<span class="settings">${f.join(", ")}</span>`}
                </div>
                <button
                  class="cancel"
                  aria-label=${l(e,"card_cancel_command")}
                  aria-describedby="command-${p}"
                  ?disabled=${c}
                  @click=${()=>{_e(e,o.entity,d.id)}}
                >
                  <span aria-hidden="true">×</span>
                </button>
              </li>
            `})}
        </ul>
      </section>
    `}#m(t,e){let{hass:o}=this,i=nt(o,t.at,e);return t.action==="off"?l(o,"card_command_off",{time:i}):t.minutes===null?l(o,"card_command_on",{time:i}):l(o,"card_command_on_for",{time:i,duration:$(o,t.minutes)})}#f(){return this.hass.user?.is_admin?h`
      <footer>
        <a href=${Yn(this.lookup.info.entry_id)} @click=${this.#g}>
          ${l(this.hass,"card_settings")}
        </a>
      </footer>
    `:u}#g=t=>{!t.ctrlKey&&!t.metaKey&&!t.shiftKey&&this.close()}};var Je="data-held",St=class{#t;#e;#n=!1;#i;#r;#o=!1;#d=!1;#a;#s=t=>this.#u(t);constructor(t,e){this.#t=t,this.#e=e,t.addController(this)}hostDisconnected(){this.#n=!1,this.#d=!1,this.#h(),this.#l()}cancelPress(){this.#l()}binding(){return{click:t=>{if(this.#d){this.#d=!1,t.preventDefault(),t.stopPropagation();return}this.#c()},keydown:t=>{t.key==="Enter"?(t.preventDefault(),t.repeat||this.#e().tap()):t.key===" "&&(t.preventDefault(),this.#n=!0)},keyup:t=>{if(t.key!==" ")return;let e=this.#n;this.#n=!1,e&&this.#e().tap()},pointerdown:t=>this.#p(t),pointerup:t=>{if(t.pointerId!==this.#i)return;let e=this.#o;this.#l();let{hold:o}=this.#e();e&&o!==void 0&&(this.#d=!0,o())},pointercancel:t=>this.#u(t),pointerleave:t=>this.#u(t),contextmenu:t=>{this.#i!==void 0&&t.preventDefault()}}}#c(){let{tap:t,doubleTap:e}=this.#e(),o=this.#a!==void 0;this.#h(),e===void 0?t():o?e():this.#a=setTimeout(()=>{this.#a=void 0,this.#e().tap()},250)}#h(){clearTimeout(this.#a),this.#a=void 0}#p(t){this.#e().hold===void 0||!t.isPrimary||t.button!==0||(this.#d=!1,this.#l(),this.#i=t.pointerId,window.addEventListener("pointerup",this.#s),window.addEventListener("pointercancel",this.#s),this.#r=setTimeout(()=>{this.#r=void 0,this.#o=!0,this.#t.setAttribute(Je,"")},500))}#u(t){t.pointerId===this.#i&&this.#l()}#l(){clearTimeout(this.#r),this.#r=void 0,this.#i=void 0,this.#o=!1,window.removeEventListener("pointerup",this.#s),window.removeEventListener("pointercancel",this.#s),this.#t.removeAttribute(Je)}};var E=80,tn=6,Zt=(E-tn)/2,Qe=2*Math.PI*Zt,Gt=20,Xn=9,Jn=Xn*100/Gt;function Qn(n){let t=h`<span class="icon">${bt(n)}</span>`;if(n.state!=="counting")return t;let e=N(n.remaining);return h`<span class="time" aria-hidden="true">${e}</span>${t}`}function en(n,t,e,o,i,r){let s=E/2,c=B(t);return h`
    <ha-card class="round ${n.state} ${t.show_turn_off?"with-turn-off":""}">
      <div
        class="body"
        role=${x(c?"button":void 0)}
        tabindex=${x(c?"0":void 0)}
        aria-haspopup=${x(vt(t))}
        aria-labelledby=${x(c?"label":void 0)}
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
          <svg class="ring" viewBox="0 0 ${E} ${E}" aria-hidden="true">
            <circle class="track" cx=${s} cy=${s} r=${Zt}></circle>
            <circle
              class="progress"
              cx=${s}
              cy=${s}
              r=${Zt}
              transform="rotate(-90 ${s} ${s})"
              stroke-dasharray=${Qe}
              stroke-dashoffset=${(1-n.progress)*Qe}
            ></circle>
          </svg>
          <span class="centre">
            ${Qn(n)}
          </span>
        </div>
        <span class="text" id="label">
          <span class="name">${n.name}</span>
          <span class="status">${wt(n,t,e,r)}</span>
        </span>
        ${t.show_turn_off?h`<div class="turn-off-slot">${$t(n,t,e,i)}</div>`:u}
      </div>
    </ha-card>
  `}var nn=y`
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
    width: ${E}px;
    height: ${E}px;
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
    stroke-width: ${tn};
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
  /*
   * While it counts the dial holds the time and the icon, and shows the time. The icon takes its
   * place only in a dial too small for the time, see the end of these styles; a browser that
   * does not know container queries never shows it. The selector is more specific than the
   * Mushroom rule that shows the icon (mushroomStyles, in layout.ts).
   */
  ha-card.round.counting .icon {
    display: none;
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
  @container (width < ${rt.round}px) {
    ${st(y`.round`)}
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
  /*
   * The Mushroom style (see mushroomStyles in layout.ts): the dial, the name and the button
   * with the spacing of Mushroom around them. The tile is as high as they make it, and never
   * lower than the rows of the grid it sits in.
   */
  :host([data-mushroom]) ha-card.round {
    height: max(120px, calc(2 * ${a.spacing} + ${E}px + ${a.primaryLineHeight}));
  }
  :host([data-mushroom]) ha-card.round.with-turn-off {
    height: max(
      184px,
      calc(
        2 * ${a.spacing} + ${E}px + ${a.primaryLineHeight} + 4px + ${a.controlHeight}
      )
    );
  }
  :host([data-mushroom]) .round .content {
    gap: 0;
    padding: ${a.spacing};
  }
  :host([data-mushroom]) .progress {
    stroke: rgb(${a.activeRgb});
  }
  :host([data-mushroom]) .time {
    color: ${a.primaryColor};
    font-size: ${a.primaryFontSize};
    font-weight: ${a.primaryFontWeight};
    letter-spacing: ${a.primaryLetterSpacing};
  }
  :host([data-mushroom]) .turn-off-slot {
    height: ${a.controlHeight};
  }
  /*
   * The dial shrinks with its tile: it is 80 px where the tile has room, and as wide as the room
   * where it has less, and the time and the icon follow it in container units. In a dial too
   * small for the time to be read (TIME_FROM, where the time is MIN_TIME_PX high) the ring and
   * the icon are shown and the time is not. The dial is the container and not .content, so that
   * a card without the Turn off button is laid out as before (see turnOffAsIcon: only a card
   * that has the button makes .content a container). All of it is one block, so that a browser
   * that does not know container units keeps the dial at 80 px with its time: a width capped
   * without an aspect ratio would not be a square, and a custom property with cqw in it is
   * invalid only where it is used.
   */
  @supports (width: 1cqw) {
    .dial {
      max-width: 100%;
      height: auto;
      aspect-ratio: 1;
      container-type: inline-size;
    }
    .round .time {
      font-size: min(var(--ha-font-size-l, 16px), ${Gt}cqw);
    }
    :host(:not([data-mushroom])) .round .icon {
      /* No line of text around a small symbol: the box of the icon is the symbol. */
      line-height: 0;
      --mdc-icon-size: min(32px, 40cqw);
    }
    :host([data-mushroom]) .round .time {
      font-size: min(${a.primaryFontSize}, ${Gt}cqw);
    }
    /* 45 % of the full dial, 80 px, is 36 px, the size of Mushroom's icon shape. */
    :host([data-mushroom]) .round .icon {
      width: min(${a.iconSize}, 45cqw);
      height: min(${a.iconSize}, 45cqw);
      font-size: min(${a.iconSize}, 45cqw);
    }
    @container (width < ${Jn}px) {
      ha-card.round.counting .time {
        display: none;
      }
      ha-card.round.counting .icon {
        display: flex;
      }
    }
  }
`;var Yt="timerify-card",at={pill:{columns:6,rows:1,min_columns:3,min_rows:1,max_rows:1},round:{columns:3,rows:2,min_columns:2,min_rows:2,max_rows:3},pillWithTurnOff:{columns:6,rows:1,min_columns:6,min_rows:1,max_rows:1},pillWithTurnOffAndChip:{columns:9,rows:1,min_columns:9,min_rows:1,max_rows:1},roundWithTurnOff:{columns:3,rows:3,min_columns:3,min_rows:3,max_rows:3}},Xt=class extends w{static properties={hass:{attribute:!1,noAccessor:!0},_config:{state:!0},_lookup:{state:!0}};static styles=[je,Ye,nn,Ve,y`
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
    `];static getConfigForm=Ie;static getStubConfig=Ne;#t;#e=new Set;#n=!1;#i=!1;#r=new St(this,()=>this.#g());#o=this.#r.binding();#d=()=>{let{_config:t,hass:e}=this;t?.chip!==void 0&&e!==void 0&&X(e,t.entity,t.chip)};#a=()=>{let{_config:t,hass:e}=this;t!==void 0&&e!==void 0&&I(e,t.entity)};#s;#c=!1;constructor(){super(),this._lookup={status:"pending"},new mt(this,()=>this.#s?.state==="counting"?this.#s.endsAt:void 0,()=>M(this._lookup)),new j(this,()=>this.#s?.state==="limit"&&this.#s.endsAt?[this.#s.endsAt]:[],()=>M(this._lookup),()=>this.#t?et(this.#t):void 0),new ft(this,()=>this._config?.mushroom===!0)}get hass(){return this.#t}set hass(t){let e=this.#t;this.#t=t,this.requestUpdate("hass",e),this.#h(e,t)}setConfig(t){let e=Re(t),o=this._config?.entity!==e.entity;this._config=e,o&&(this._lookup={status:"pending"},this.#u())}getCardSize(){return this._config?.layout!=="round"?1:this._config.show_turn_off?4:3}getGridOptions(){let t=this._config;return t?.layout==="round"?t.show_turn_off?at.roundWithTurnOff:at.round:t?.show_turn_off?t.chip===void 0?at.pillWithTurnOff:at.pillWithTurnOffAndChip:at.pill}async getUpdateComplete(){let t=await super.getUpdateComplete();for(;this.#e.size>0;)await Promise.allSettled([...this.#e]),t=await super.getUpdateComplete();return t}#h(t,e){let o=t!==void 0&&e.connected&&!t.connected;(t===void 0||t.language!==e.language||o)&&this.#p(pt(e));let i=this._config?.entity;i!==void 0&&(t===void 0||t.entities!==e.entities||o||U(e.states[i])&&!U(t.states[i]))&&this.#u()}#p(t){let e=t.finally(()=>this.#e.delete(e));this.#e.add(e)}#u(){if(this.#n){this.#i=!0;return}this.#n=!0,this.#p(this.#l())}async#l(){try{do{this.#i=!1;let t=this._config?.entity;if(this.#t===void 0||t===void 0)return;let e=await Fe(this.#t,t);this.#i||(this._lookup=e)}while(this.#i)}finally{this.#n=!1}}willUpdate(){this.#c=this.shadowRoot?.activeElement?.classList.contains("turn-off")===!0}updated(){this.#c&&this.shadowRoot?.querySelector(".turn-off")===null&&this.#m()}#m(){let t=this._config;t!==void 0&&B(t)&&this.renderRoot.querySelector(".body")?.focus()}shouldUpdate(t){let e=this._lookup.status==="found"?this._lookup.info:void 0,o=this._config?_t(this._config.entity,e):[];return yt(t,this.#t,o)}get#f(){return this.renderRoot.querySelector("timerify-card-popup")}#g(){let t=this._config,e={tap:()=>this.#_("tap")};return t!==void 0&&t.double_tap!=="none"&&(e.doubleTap=()=>this.#_("double_tap")),t!==void 0&&t.hold!=="none"&&(e.hold=()=>this.#_("hold")),e}#_(t){let{_config:e,hass:o}=this;if(!(e===void 0||o===void 0))switch(e[t]){case"popup":this.#r.cancelPress(),this.#f?.open();break;case"run":Nt(o,e.entity);break;case"stop":I(o,e.entity);break;case"run_or_stop":this.#y(o,e);break;case"action":this.#b(t,e);break;case"none":break}}#y(t,e){let o=this.#s;o!==void 0&&(F(o)?I(t,e.entity):o.state==="idle"&&Nt(t,e.entity))}#b(t,e){if(this._lookup.status!=="found")return;let o=Object.fromEntries(Vt.filter(i=>e[i]!==void 0).map(i=>[i,e[i]]));this.dispatchEvent(new CustomEvent("hass-action",{detail:{config:{entity:this._lookup.info.target,...o},action:t},bubbles:!0,composed:!0}))}#v(t,e){let o=this._lookup;if(o.status==="unauthorized")return l(t,"card_not_allowed",{entity:e.entity});if(o.status==="incomplete")return l(t,"card_timer_incomplete",{entity:e.entity});if(o.status==="found"&&gt(o.info,o.info.ends_at))return l(t,"card_ends_at_disabled",{sensor:o.info.ends_at});if(o.status!=="not_found")return;let i=t.states[e.entity];return i===void 0?l(t,"card_entity_not_found",{entity:e.entity}):U(i)?l(t,"card_not_a_timer",{entity:e.entity}):void 0}render(){let t=this.#t,e=this._config;if(!t||!e)return u;let o=this.#v(t,e);if(o)return this.#s=void 0,h`
        <ha-card>
          <div class="warning" role="alert">
            <ha-icon icon="mdi:alert-outline"></ha-icon>
            <span>${o}</span>
          </div>
        </ha-card>
      `;let i=M(this._lookup),r=Be(t,e,this._lookup,i);return this.#s=r,h`
      ${e.layout==="round"?en(r,e,t,this.#o,this.#a,i):Ge(r,e,t,this.#o,this.#d,this.#a,i)}
      ${this._lookup.status==="found"?h`
            <timerify-card-popup
              .hass=${t}
              .config=${e}
              .lookup=${this._lookup}
              .view=${r}
              @closed=${()=>this.#m()}
            ></timerify-card-popup>
          `:u}
    `}};if(!customElements.get(Yt)){customElements.define("timerify-card-popup",At),customElements.define(Yt,Xt);let n={type:Yt,name:"Timerify",description:l(void 0,"card_picker_description"),preview:!0,documentationURL:"https://github.com/klimofey/timerify#dashboard-card"};(window.customCards??=[]).push(n),Ae(()=>{n.description=l(H(),"card_picker_description")})}export{Xt as TimerifyCard};
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
