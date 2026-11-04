var it=globalThis,rt=it.ShadowRoot&&(it.ShadyCSS===void 0||it.ShadyCSS.nativeShadow)&&"adoptedStyleSheets"in Document.prototype&&"replace"in CSSStyleSheet.prototype,wt=Symbol(),qt=new WeakMap,F=class{constructor(t,e,n){if(this._$cssResult$=!0,n!==wt)throw Error("CSSResult is not constructable. Use `unsafeCSS` or `css` instead.");this.cssText=t,this.t=e}get styleSheet(){let t=this.o,e=this.t;if(rt&&t===void 0){let n=e!==void 0&&e.length===1;n&&(t=qt.get(e)),t===void 0&&((this.o=t=new CSSStyleSheet).replaceSync(this.cssText),n&&qt.set(e,t))}return t}toString(){return this.cssText}},st=o=>new F(typeof o=="string"?o:o+"",void 0,wt),y=(o,...t)=>{let e=o.length===1?o[0]:t.reduce((n,i,r)=>n+(s=>{if(s._$cssResult$===!0)return s.cssText;if(typeof s=="number")return s;throw Error("Value passed to 'css' function must be a 'css' function result: "+s+". Use 'unsafeCSS' to pass non-literal values, but take care to ensure page security.")})(i)+o[r+1],o[0]);return new F(e,o,wt)},Gt=(o,t)=>{if(rt)o.adoptedStyleSheets=t.map(e=>e instanceof CSSStyleSheet?e:e.styleSheet);else for(let e of t){let n=document.createElement("style"),i=it.litNonce;i!==void 0&&n.setAttribute("nonce",i),n.textContent=e.cssText,o.appendChild(n)}},xt=rt?o=>o:o=>o instanceof CSSStyleSheet?(t=>{let e="";for(let n of t.cssRules)e+=n.cssText;return st(e)})(o):o;var{is:Ze,defineProperty:Je,getOwnPropertyDescriptor:Qe,getOwnPropertyNames:to,getOwnPropertySymbols:eo,getPrototypeOf:oo}=Object,at=globalThis,Yt=at.trustedTypes,no=Yt?Yt.emptyScript:"",io=at.reactiveElementPolyfillSupport,B=(o,t)=>o,At={toAttribute(o,t){switch(t){case Boolean:o=o?no:null;break;case Object:case Array:o=o==null?o:JSON.stringify(o)}return o},fromAttribute(o,t){let e=o;switch(t){case Boolean:e=o!==null;break;case Number:e=o===null?null:Number(o);break;case Object:case Array:try{e=JSON.parse(o)}catch{e=null}}return e}},Zt=(o,t)=>!Ze(o,t),Xt={attribute:!0,type:String,converter:At,reflect:!1,useDefault:!1,hasChanged:Zt};Symbol.metadata??=Symbol("metadata"),at.litPropertyMetadata??=new WeakMap;var A=class extends HTMLElement{static addInitializer(t){this._$Ei(),(this.l??=[]).push(t)}static get observedAttributes(){return this.finalize(),this._$Eh&&[...this._$Eh.keys()]}static createProperty(t,e=Xt){if(e.state&&(e.attribute=!1),this._$Ei(),this.prototype.hasOwnProperty(t)&&((e=Object.create(e)).wrapped=!0),this.elementProperties.set(t,e),!e.noAccessor){let n=Symbol(),i=this.getPropertyDescriptor(t,n,e);i!==void 0&&Je(this.prototype,t,i)}}static getPropertyDescriptor(t,e,n){let{get:i,set:r}=Qe(this.prototype,t)??{get(){return this[e]},set(s){this[e]=s}};return{get:i,set(s){let c=i?.call(this);r?.call(this,s),this.requestUpdate(t,c,n)},configurable:!0,enumerable:!0}}static getPropertyOptions(t){return this.elementProperties.get(t)??Xt}static _$Ei(){if(this.hasOwnProperty(B("elementProperties")))return;let t=oo(this);t.finalize(),t.l!==void 0&&(this.l=[...t.l]),this.elementProperties=new Map(t.elementProperties)}static finalize(){if(this.hasOwnProperty(B("finalized")))return;if(this.finalized=!0,this._$Ei(),this.hasOwnProperty(B("properties"))){let e=this.properties,n=[...to(e),...eo(e)];for(let i of n)this.createProperty(i,e[i])}let t=this[Symbol.metadata];if(t!==null){let e=litPropertyMetadata.get(t);if(e!==void 0)for(let[n,i]of e)this.elementProperties.set(n,i)}this._$Eh=new Map;for(let[e,n]of this.elementProperties){let i=this._$Eu(e,n);i!==void 0&&this._$Eh.set(i,e)}this.elementStyles=this.finalizeStyles(this.styles)}static finalizeStyles(t){let e=[];if(Array.isArray(t)){let n=new Set(t.flat(1/0).reverse());for(let i of n)e.unshift(xt(i))}else t!==void 0&&e.push(xt(t));return e}static _$Eu(t,e){let n=e.attribute;return n===!1?void 0:typeof n=="string"?n:typeof t=="string"?t.toLowerCase():void 0}constructor(){super(),this._$Ep=void 0,this.isUpdatePending=!1,this.hasUpdated=!1,this._$Em=null,this._$Ev()}_$Ev(){this._$ES=new Promise(t=>this.enableUpdating=t),this._$AL=new Map,this._$E_(),this.requestUpdate(),this.constructor.l?.forEach(t=>t(this))}addController(t){(this._$EO??=new Set).add(t),this.renderRoot!==void 0&&this.isConnected&&t.hostConnected?.()}removeController(t){this._$EO?.delete(t)}_$E_(){let t=new Map,e=this.constructor.elementProperties;for(let n of e.keys())this.hasOwnProperty(n)&&(t.set(n,this[n]),delete this[n]);t.size>0&&(this._$Ep=t)}createRenderRoot(){let t=this.shadowRoot??this.attachShadow(this.constructor.shadowRootOptions);return Gt(t,this.constructor.elementStyles),t}connectedCallback(){this.renderRoot??=this.createRenderRoot(),this.enableUpdating(!0),this._$EO?.forEach(t=>t.hostConnected?.())}enableUpdating(t){}disconnectedCallback(){this._$EO?.forEach(t=>t.hostDisconnected?.())}attributeChangedCallback(t,e,n){this._$AK(t,n)}_$ET(t,e){let n=this.constructor.elementProperties.get(t),i=this.constructor._$Eu(t,n);if(i!==void 0&&n.reflect===!0){let r=(n.converter?.toAttribute!==void 0?n.converter:At).toAttribute(e,n.type);this._$Em=t,r==null?this.removeAttribute(i):this.setAttribute(i,r),this._$Em=null}}_$AK(t,e){let n=this.constructor,i=n._$Eh.get(t);if(i!==void 0&&this._$Em!==i){let r=n.getPropertyOptions(i),s=typeof r.converter=="function"?{fromAttribute:r.converter}:r.converter?.fromAttribute!==void 0?r.converter:At;this._$Em=i;let c=s.fromAttribute(e,r.type);this[i]=c??this._$Ej?.get(i)??c,this._$Em=null}}requestUpdate(t,e,n,i=!1,r){if(t!==void 0){let s=this.constructor;if(i===!1&&(r=this[t]),n??=s.getPropertyOptions(t),!((n.hasChanged??Zt)(r,e)||n.useDefault&&n.reflect&&r===this._$Ej?.get(t)&&!this.hasAttribute(s._$Eu(t,n))))return;this.C(t,e,n)}this.isUpdatePending===!1&&(this._$ES=this._$EP())}C(t,e,{useDefault:n,reflect:i,wrapped:r},s){n&&!(this._$Ej??=new Map).has(t)&&(this._$Ej.set(t,s??e??this[t]),r!==!0||s!==void 0)||(this._$AL.has(t)||(this.hasUpdated||n||(e=void 0),this._$AL.set(t,e)),i===!0&&this._$Em!==t&&(this._$Eq??=new Set).add(t))}async _$EP(){this.isUpdatePending=!0;try{await this._$ES}catch(e){Promise.reject(e)}let t=this.scheduleUpdate();return t!=null&&await t,!this.isUpdatePending}scheduleUpdate(){return this.performUpdate()}performUpdate(){if(!this.isUpdatePending)return;if(!this.hasUpdated){if(this.renderRoot??=this.createRenderRoot(),this._$Ep){for(let[i,r]of this._$Ep)this[i]=r;this._$Ep=void 0}let n=this.constructor.elementProperties;if(n.size>0)for(let[i,r]of n){let{wrapped:s}=r,c=this[i];s!==!0||this._$AL.has(i)||c===void 0||this.C(i,void 0,r,c)}}let t=!1,e=this._$AL;try{t=this.shouldUpdate(e),t?(this.willUpdate(e),this._$EO?.forEach(n=>n.hostUpdate?.()),this.update(e)):this._$EM()}catch(n){throw t=!1,this._$EM(),n}t&&this._$AE(e)}willUpdate(t){}_$AE(t){this._$EO?.forEach(e=>e.hostUpdated?.()),this.hasUpdated||(this.hasUpdated=!0,this.firstUpdated(t)),this.updated(t)}_$EM(){this._$AL=new Map,this.isUpdatePending=!1}get updateComplete(){return this.getUpdateComplete()}getUpdateComplete(){return this._$ES}shouldUpdate(t){return!0}update(t){this._$Eq&&=this._$Eq.forEach(e=>this._$ET(e,this[e])),this._$EM()}updated(t){}firstUpdated(t){}};A.elementStyles=[],A.shadowRootOptions={mode:"open"},A[B("elementProperties")]=new Map,A[B("finalized")]=new Map,io?.({ReactiveElement:A}),(at.reactiveElementVersions??=[]).push("2.1.2");var Rt=globalThis,Jt=o=>o,dt=Rt.trustedTypes,Qt=dt?dt.createPolicy("lit-html",{createHTML:o=>o}):void 0,re="$lit$",C=`lit$${Math.random().toFixed(9).slice(2)}$`,se="?"+C,ro=`<${se}>`,R=document,V=()=>R.createComment(""),W=o=>o===null||typeof o!="object"&&typeof o!="function",Ht=Array.isArray,so=o=>Ht(o)||typeof o?.[Symbol.iterator]=="function",St=`[ 	
\f\r]`,j=/<(?:(!--|\/[^a-zA-Z])|(\/?[a-zA-Z][^>\s]*)|(\/?$))/g,te=/-->/g,ee=/>/g,T=RegExp(`>|${St}(?:([^\\s"'>=/]+)(${St}*=${St}*(?:[^ 	
\f\r"'\`<>=]|("|')|))|$)`,"g"),oe=/'/g,ne=/"/g,ae=/^(?:script|style|textarea|title)$/i,Ot=o=>(t,...e)=>({_$litType$:o,strings:t,values:e}),p=Ot(1),Xo=Ot(2),Zo=Ot(3),S=Symbol.for("lit-noChange"),u=Symbol.for("lit-nothing"),ie=new WeakMap,P=R.createTreeWalker(R,129);function de(o,t){if(!Ht(o)||!o.hasOwnProperty("raw"))throw Error("invalid template strings array");return Qt!==void 0?Qt.createHTML(t):t}var ao=(o,t)=>{let e=o.length-1,n=[],i,r=t===2?"<svg>":t===3?"<math>":"",s=j;for(let c=0;c<e;c++){let d=o[c],h,f,m=-1,b=0;for(;b<d.length&&(s.lastIndex=b,f=s.exec(d),f!==null);)b=s.lastIndex,s===j?f[1]==="!--"?s=te:f[1]!==void 0?s=ee:f[2]!==void 0?(ae.test(f[2])&&(i=RegExp("</"+f[2],"g")),s=T):f[3]!==void 0&&(s=T):s===T?f[0]===">"?(s=i??j,m=-1):f[1]===void 0?m=-2:(m=s.lastIndex-f[2].length,h=f[1],s=f[3]===void 0?T:f[3]==='"'?ne:oe):s===ne||s===oe?s=T:s===te||s===ee?s=j:(s=T,i=void 0);let v=s===T&&o[c+1].startsWith("/>")?" ":"";r+=s===j?d+ro:m>=0?(n.push(h),d.slice(0,m)+re+d.slice(m)+C+v):d+C+(m===-2?c:v)}return[de(o,r+(o[e]||"<?>")+(t===2?"</svg>":t===3?"</math>":"")),n]},K=class o{constructor({strings:t,_$litType$:e},n){let i;this.parts=[];let r=0,s=0,c=t.length-1,d=this.parts,[h,f]=ao(t,e);if(this.el=o.createElement(h,n),P.currentNode=this.el.content,e===2||e===3){let m=this.el.content.firstChild;m.replaceWith(...m.childNodes)}for(;(i=P.nextNode())!==null&&d.length<c;){if(i.nodeType===1){if(i.hasAttributes())for(let m of i.getAttributeNames())if(m.endsWith(re)){let b=f[s++],v=i.getAttribute(m).split(C),k=/([.?@])?(.*)/.exec(b);d.push({type:1,index:r,name:k[2],strings:v,ctor:k[1]==="."?Et:k[1]==="?"?kt:k[1]==="@"?Tt:M}),i.removeAttribute(m)}else m.startsWith(C)&&(d.push({type:6,index:r}),i.removeAttribute(m));if(ae.test(i.tagName)){let m=i.textContent.split(C),b=m.length-1;if(b>0){i.textContent=dt?dt.emptyScript:"";for(let v=0;v<b;v++)i.append(m[v],V()),P.nextNode(),d.push({type:2,index:++r});i.append(m[b],V())}}}else if(i.nodeType===8)if(i.data===se)d.push({type:2,index:r});else{let m=-1;for(;(m=i.data.indexOf(C,m+1))!==-1;)d.push({type:7,index:r}),m+=C.length-1}r++}}static createElement(t,e){let n=R.createElement("template");return n.innerHTML=t,n}};function O(o,t,e=o,n){if(t===S)return t;let i=n!==void 0?e._$Co?.[n]:e._$Cl,r=W(t)?void 0:t._$litDirective$;return i?.constructor!==r&&(i?._$AO?.(!1),r===void 0?i=void 0:(i=new r(o),i._$AT(o,e,n)),n!==void 0?(e._$Co??=[])[n]=i:e._$Cl=i),i!==void 0&&(t=O(o,i._$AS(o,t.values),i,n)),t}var Ct=class{constructor(t,e){this._$AV=[],this._$AN=void 0,this._$AD=t,this._$AM=e}get parentNode(){return this._$AM.parentNode}get _$AU(){return this._$AM._$AU}u(t){let{el:{content:e},parts:n}=this._$AD,i=(t?.creationScope??R).importNode(e,!0);P.currentNode=i;let r=P.nextNode(),s=0,c=0,d=n[0];for(;d!==void 0;){if(s===d.index){let h;d.type===2?h=new q(r,r.nextSibling,this,t):d.type===1?h=new d.ctor(r,d.name,d.strings,this,t):d.type===6&&(h=new Pt(r,this,t)),this._$AV.push(h),d=n[++c]}s!==d?.index&&(r=P.nextNode(),s++)}return P.currentNode=R,i}p(t){let e=0;for(let n of this._$AV)n!==void 0&&(n.strings!==void 0?(n._$AI(t,n,e),e+=n.strings.length-2):n._$AI(t[e])),e++}},q=class o{get _$AU(){return this._$AM?._$AU??this._$Cv}constructor(t,e,n,i){this.type=2,this._$AH=u,this._$AN=void 0,this._$AA=t,this._$AB=e,this._$AM=n,this.options=i,this._$Cv=i?.isConnected??!0}get parentNode(){let t=this._$AA.parentNode,e=this._$AM;return e!==void 0&&t?.nodeType===11&&(t=e.parentNode),t}get startNode(){return this._$AA}get endNode(){return this._$AB}_$AI(t,e=this){t=O(this,t,e),W(t)?t===u||t==null||t===""?(this._$AH!==u&&this._$AR(),this._$AH=u):t!==this._$AH&&t!==S&&this._(t):t._$litType$!==void 0?this.$(t):t.nodeType!==void 0?this.T(t):so(t)?this.k(t):this._(t)}O(t){return this._$AA.parentNode.insertBefore(t,this._$AB)}T(t){this._$AH!==t&&(this._$AR(),this._$AH=this.O(t))}_(t){this._$AH!==u&&W(this._$AH)?this._$AA.nextSibling.data=t:this.T(R.createTextNode(t)),this._$AH=t}$(t){let{values:e,_$litType$:n}=t,i=typeof n=="number"?this._$AC(t):(n.el===void 0&&(n.el=K.createElement(de(n.h,n.h[0]),this.options)),n);if(this._$AH?._$AD===i)this._$AH.p(e);else{let r=new Ct(i,this),s=r.u(this.options);r.p(e),this.T(s),this._$AH=r}}_$AC(t){let e=ie.get(t.strings);return e===void 0&&ie.set(t.strings,e=new K(t)),e}k(t){Ht(this._$AH)||(this._$AH=[],this._$AR());let e=this._$AH,n,i=0;for(let r of t)i===e.length?e.push(n=new o(this.O(V()),this.O(V()),this,this.options)):n=e[i],n._$AI(r),i++;i<e.length&&(this._$AR(n&&n._$AB.nextSibling,i),e.length=i)}_$AR(t=this._$AA.nextSibling,e){for(this._$AP?.(!1,!0,e);t!==this._$AB;){let n=Jt(t).nextSibling;Jt(t).remove(),t=n}}setConnected(t){this._$AM===void 0&&(this._$Cv=t,this._$AP?.(t))}},M=class{get tagName(){return this.element.tagName}get _$AU(){return this._$AM._$AU}constructor(t,e,n,i,r){this.type=1,this._$AH=u,this._$AN=void 0,this.element=t,this.name=e,this._$AM=i,this.options=r,n.length>2||n[0]!==""||n[1]!==""?(this._$AH=Array(n.length-1).fill(new String),this.strings=n):this._$AH=u}_$AI(t,e=this,n,i){let r=this.strings,s=!1;if(r===void 0)t=O(this,t,e,0),s=!W(t)||t!==this._$AH&&t!==S,s&&(this._$AH=t);else{let c=t,d,h;for(t=r[0],d=0;d<r.length-1;d++)h=O(this,c[n+d],e,d),h===S&&(h=this._$AH[d]),s||=!W(h)||h!==this._$AH[d],h===u?t=u:t!==u&&(t+=(h??"")+r[d+1]),this._$AH[d]=h}s&&!i&&this.j(t)}j(t){t===u?this.element.removeAttribute(this.name):this.element.setAttribute(this.name,t??"")}},Et=class extends M{constructor(){super(...arguments),this.type=3}j(t){this.element[this.name]=t===u?void 0:t}},kt=class extends M{constructor(){super(...arguments),this.type=4}j(t){this.element.toggleAttribute(this.name,!!t&&t!==u)}},Tt=class extends M{constructor(t,e,n,i,r){super(t,e,n,i,r),this.type=5}_$AI(t,e=this){if((t=O(this,t,e,0)??u)===S)return;let n=this._$AH,i=t===u&&n!==u||t.capture!==n.capture||t.once!==n.once||t.passive!==n.passive,r=t!==u&&(n===u||i);i&&this.element.removeEventListener(this.name,this,n),r&&this.element.addEventListener(this.name,this,t),this._$AH=t}handleEvent(t){typeof this._$AH=="function"?this._$AH.call(this.options?.host??this.element,t):this._$AH.handleEvent(t)}},Pt=class{constructor(t,e,n){this.element=t,this.type=6,this._$AN=void 0,this._$AM=e,this.options=n}get _$AU(){return this._$AM._$AU}_$AI(t){O(this,t)}};var co=Rt.litHtmlPolyfillSupport;co?.(K,q),(Rt.litHtmlVersions??=[]).push("3.3.3");var ce=(o,t,e)=>{let n=e?.renderBefore??t,i=n._$litPart$;if(i===void 0){let r=e?.renderBefore??null;n._$litPart$=i=new q(t.insertBefore(V(),r),r,void 0,e??{})}return i._$AI(o),i};var Mt=globalThis,w=class extends A{constructor(){super(...arguments),this.renderOptions={host:this},this._$Do=void 0}createRenderRoot(){let t=super.createRenderRoot();return this.renderOptions.renderBefore??=t.firstChild,t}update(t){let e=this.render();this.hasUpdated||(this.renderOptions.isConnected=this.isConnected),super.update(t),this._$Do=ce(e,this.renderRoot,this.renderOptions)}connectedCallback(){super.connectedCallback(),this._$Do?.setConnected(!0)}disconnectedCallback(){super.disconnectedCallback(),this._$Do?.setConnected(!1)}render(){return S}};w._$litElement$=!0,w.finalized=!0,Mt.litElementHydrateSupport?.({LitElement:w});var lo=Mt.litElementPolyfillSupport;lo?.({LitElement:w});(Mt.litElementVersions??=[]).push("4.2.2");async function z(o,t,e,n,i){try{await o.callService(t,e,n,{entity_id:i})}catch{}}function le(o,t,e){return z(o,"number","set_value",{value:e},t)}function G(o,t,e){return z(o,"timerify","add_time",{minutes:e},t)}function zt(o,t){return z(o,"timerify","run",{},t)}function L(o,t){return z(o,"timerify","stop",{},t)}function ue(o,t,e){return z(o,"switch",e?"turn_on":"turn_off",{},t)}function pe(o,t,e){return z(o,"timerify","cancel_command",{command_id:e},t)}var he={card_language:"en",card_entity_not_found:"Entity not found: {entity}",card_not_a_timer:"{entity} is not the Run for number of a Timerify timer",card_timer_incomplete:"The timer of {entity} cannot be shown: its target or one of its sensors is missing. Open the timer's page to see why.",card_not_allowed:"You are not allowed to see the timer {entity}",card_ends_at_disabled:"The Ends at sensor of this timer, {sensor}, is disabled. Enable it for the card to work",card_error_entity:"Choose the Run for number of a timer",card_error_layout:"The layout is pill or round",card_error_presets:"Presets are whole minutes from 1 to 1440",card_error_chip:"The quick chip is whole minutes from 1 to 1440",card_error_press:"Tap, double tap and hold can each be popup, run, stop, run_or_stop, action or none",card_error_action:"A Home Assistant action is a set of settings, such as action: more-info",card_error_show_turn_off:"show_turn_off is true or false",card_error_mushroom:"mushroom is true or false",card_close:"Close",card_until:"until {time}",card_until_latest:"by {time} at the latest",card_add_time:"Add {duration}",card_subtract_time:"Take off {duration}",card_presets_above_maximum:"Every preset is longer than this timer's maximum of {maximum}.",card_stop:"Stop",card_turn_off:"Turn off",card_schedule:"Schedule",card_commands:"Pending commands",card_commands_disabled:"Pending commands are hidden: the Next command sensor, {sensor}, is disabled",card_command_on:"On at {time}",card_command_on_for:"On at {time} for {duration}",card_command_off:"Off at {time}",card_cancel_command:"Cancel",card_settings:"Settings",card_picker_description:"The countdown, presets and schedule of a Timerify timer",card_editor_entity:"Timer",card_editor_layout:"Layout",card_editor_layout_pill:"Pill",card_editor_layout_round:"Round",card_editor_name:"Name",card_editor_icon:"Icon",card_editor_presets:"Duration presets (minutes)",card_editor_presets_helper:"Leave empty for {presets}",card_editor_chip:"Quick add chip (minutes, pill only)",card_editor_show_turn_off:"Show a Turn off button",card_editor_mushroom:"Mushroom style",card_editor_mushroom_missing:"Mushroom was not found. The card keeps the Home Assistant look.",card_editor_interactions:"Interactions",card_editor_tap:"Tap behavior",card_editor_double_tap:"Double tap behavior",card_editor_hold:"Hold behavior",card_editor_tap_action:"Tap action",card_editor_double_tap_action:"Double tap action",card_editor_hold_action:"Hold action",card_editor_press_popup:"Open the pop-up",card_editor_press_run:"Run",card_editor_press_stop:"Stop",card_editor_press_run_or_stop:"Start or stop",card_editor_press_action:"Home Assistant action",card_editor_press_none:"Nothing",card_editor_press_helper:"Empty: runs the action below if one is set. Otherwise it does the default.",card_editor_action_helper:'Used when the behavior above is "Home Assistant action" or empty.'};var fe="common",ge="timerify",uo=`component.${ge}.${fe}.`;function Lt(o){return uo+o}function po(o,t){return o.replace(/\{(\w+)\}/g,(e,n)=>String(t?.[n]??e))}function l(o,t,e){return o?.localize(Lt(t),e)||po(he[t],e)}var Y,me=Promise.resolve(),_e,ye=new Set;function ct(o){return o.language!==Y&&(Y=o.language,me=ho(o,o.language)),me}async function ho(o,t){let e;try{e=await o.loadBackendTranslation(fe,ge)}catch{Y===t&&(Y=void 0);return}Y===t&&(_e={...o,localize:e},ye.forEach(n=>n()))}function H(){return _e}function be(o){ye.add(o)}var X=[15,30,45,60,120],Dt=1440,Nt=["popup","run","stop","run_or_stop","action","none"],Ut=["tap","double_tap","hold"],It=["tap_action","double_tap_action","hold_action"],mo={tap:"tap_action",double_tap:"double_tap_action",hold:"hold_action"},_=class extends Error{constructor(e){super(l(H(),e));this.key=e}key};function we(o){let t=typeof o=="number"?o:typeof o=="string"&&/^\d+$/.test(o)?Number(o):void 0;return t!==void 0&&Number.isInteger(t)&&t>=1&&t<=Dt?t:void 0}function fo(o){if(o===void 0||Array.isArray(o)&&o.length===0)return[...X];if(!Array.isArray(o))throw new _("card_error_presets");let t=new Set;for(let e of o){let n=we(e);if(n===void 0)throw new _("card_error_presets");t.add(n)}return[...t]}function go(o){if(o===void 0)return;let t=we(o);if(t===void 0)throw new _("card_error_chip");return t}var xe=o=>typeof o=="object"&&o!==null?o:{},_o=o=>Nt.some(t=>t===o);function yo(o){let t=o?.action;return typeof t=="string"&&t!==""?t:void 0}function bo(o,t,e){let n=yo(t);if(o===void 0)return n===void 0?e:n==="none"?"none":"action";if(!_o(o))throw new _("card_error_press");return o==="action"&&n==="none"?"none":o}function ve(o,t){if(o===void 0)return!1;if(typeof o!="boolean")throw new _(t);return o}var vo=o=>typeof o=="object"&&o!==null&&!Array.isArray(o);function Ae(o){let t={};for(let e of It){let n=o[e];if(n!==void 0){if(!vo(n))throw new _("card_error_action");t[e]=n}}return t}var $e=o=>typeof o=="number"||typeof o=="string";function Se(o){let t=xe(o),{entity:e,layout:n,presets:i,chip:r}=t;if(e!==void 0&&typeof e!="string")throw new _("card_error_entity");if(n!==void 0&&typeof n!="string")throw new _("card_error_layout");if(i!==void 0&&!(Array.isArray(i)&&i.every($e)))throw new _("card_error_presets");if(r!==void 0&&!$e(r))throw new _("card_error_chip");if(t.show_turn_off!==void 0&&typeof t.show_turn_off!="boolean")throw new _("card_error_show_turn_off");if(t.mushroom!==void 0&&typeof t.mushroom!="boolean")throw new _("card_error_mushroom");for(let s of Ut)if(t[s]!==void 0&&typeof t[s]!="string")throw new _("card_error_press");Ae(t)}function Ce(o){let t=xe(o),{entity:e,layout:n="pill",name:i,icon:r}=t;if(typeof e!="string"||!/^number\.[a-z0-9_]+$/.test(e))throw new _("card_error_entity");if(n!=="pill"&&n!=="round")throw new _("card_error_layout");let s=go(t.chip),c=Ae(t),d=(h,f)=>bo(t[h],c[mo[h]],f);return{entity:e,layout:n,...typeof i=="string"&&i!==""&&{name:i},...typeof r=="string"&&r!==""&&{icon:r},presets:fo(t.presets),...s!==void 0&&{chip:s},show_turn_off:ve(t.show_turn_off,"card_error_show_turn_off"),mushroom:ve(t.mushroom,"card_error_mushroom"),tap:d("tap","popup"),double_tap:d("double_tap","none"),hold:d("hold",n==="round"?"run_or_stop":"none"),...c}}var lt=class{#t;#e;#o;#n=!1;#i;constructor(t,e,n){this.#t=t,this.#e=e,this.#o=n,t.addController(this)}hostConnected(){this.#n=!0,this.#r()}hostUpdated(){this.#r()}hostDisconnected(){this.#n=!1,this.#r()}#r(){let t=this.#e(),e=this.#n&&t!==void 0&&t.getTime()>this.#o();e&&this.#i===void 0?this.#i=setInterval(()=>this.#t.requestUpdate(),1e3):!e&&this.#i!==void 0&&(clearInterval(this.#i),this.#i=void 0)}};var Ee=o=>String(o).padStart(2,"0");function D(o){let t=Math.ceil(Math.max(0,o)),e=Math.floor(t/3600),n=Math.floor(t%3600/60),i=Ee(t%60);return e>0?`${e}:${Ee(n)}:${i}`:`${n}:${i}`}function $o({language:o,time_format:t}){if(t==="12"||t==="24")return t==="12";let e=new Intl.DateTimeFormat(t==="language"?o:void 0,{hour:"numeric"}).resolvedOptions();return e.hourCycle==="h11"||e.hourCycle==="h12"}var wo=864e5;function ke(o,t){let e=new Intl.DateTimeFormat("en-US",{timeZone:o,year:"numeric",month:"numeric",day:"numeric"}).formatToParts(t),n=i=>Number(e.find(r=>r.type===i)?.value);return Date.UTC(n("year"),n("month")-1,n("day"))/wo}function Z(o,t,e){let{locale:n}=o,i=n.time_zone==="server"?o.config.time_zone:void 0,r=ke(i,t.getTime())-ke(i,e),s=r===0?{}:r>=1&&r<=6?{weekday:"short"}:{month:"short",day:"numeric"};return new Intl.DateTimeFormat(n.language,{...s,hour:"numeric",minute:"2-digit",hourCycle:$o(n)?"h12":"h23",timeZone:i}).format(t)}function $(o,t){let e=(s,c)=>new Intl.NumberFormat(o.locale.language,{style:"unit",unit:c,unitDisplay:"short",useGrouping:!1}).format(s),n=Math.floor(t/60),i=t%60,r=n>0?[e(n,"hour")]:[];return(i>0||n===0)&&r.push(e(i,"minute")),r.join(" ")}function Te(o,t,e,n,i){return e.includes(n)&&typeof i=="number"?new Intl.NumberFormat(o.locale.language,{style:"percent",maximumFractionDigits:1}).format(i/100):t===void 0?String(i):n==="hvac_mode"?o.formatEntityState(t,String(i)):o.formatEntityAttributeValue(t,n,i)}var Re="mushroom-entity-card",xo="data-mushroom",g=(o,t)=>st(`var(--mush-${o}, ${t})`),a={spacing:g("spacing","10px"),iconSize:g("icon-size","36px"),iconRadius:g("icon-border-radius","50%"),iconSymbolSize:g("icon-symbol-size","0.667em"),primaryColor:g("card-primary-color","var(--primary-text-color)"),primaryFontSize:g("card-primary-font-size","14px"),primaryFontWeight:g("card-primary-font-weight","500"),primaryLineHeight:g("card-primary-line-height","20px"),primaryLetterSpacing:g("card-primary-letter-spacing","0.1px"),secondaryColor:g("card-secondary-color","var(--primary-text-color)"),secondaryFontSize:g("card-secondary-font-size","12px"),secondaryFontWeight:g("card-secondary-font-weight","400"),secondaryLineHeight:g("card-secondary-line-height","16px"),secondaryLetterSpacing:g("card-secondary-letter-spacing","0.4px"),controlHeight:g("control-height","42px"),controlRadius:g("control-border-radius","12px"),controlButtonRatio:g("control-button-ratio","1"),controlIconSize:g("control-icon-size","0.5em"),controlSpacing:g("control-spacing","12px"),chipHeight:g("chip-height","36px"),chipRadius:g("chip-border-radius","19px"),chipPadding:g("chip-padding","0 0.25em"),chipFontSize:g("chip-font-size","0.3em"),chipFontWeight:g("chip-font-weight","bold"),chipBorderWidth:g("chip-border-width","var(--ha-card-border-width, 1px)"),chipBorderColor:g("chip-border-color","var(--ha-card-border-color, var(--divider-color, #e0e0e0))"),chipBoxShadow:g("chip-box-shadow","var(--ha-card-box-shadow, none)"),chipBackground:g("chip-background","var(--ha-card-background, var(--card-background-color, white))"),activeRgb:g("rgb-state-entity","var(--mush-rgb-blue, 33, 150, 243)"),disabledRgb:g("rgb-disabled","var(--rgb-disabled-text-color, 189, 189, 189)")},Ft=()=>customElements.get(Re)!==void 0,J=new Set,Pe=!1;function Ao(o){J.add(o),!Pe&&(Pe=!0,customElements.whenDefined(Re).then(()=>{for(let t of J)t.requestUpdate();J.clear()}))}var ut=class{#t;#e;constructor(t,e){this.#t=t,this.#e=e,t.addController(this)}hostConnected(){this.#o()}hostUpdate(){this.#o()}hostDisconnected(){J.delete(this.#t)}#o(){let t=this.#e(),e=Ft();this.#t.toggleAttribute(xo,t&&e),t&&!e&&this.#t.isConnected?Ao(this.#t):J.delete(this.#t)}};var He={entity:"card_editor_entity",layout:"card_editor_layout",name:"card_editor_name",icon:"card_editor_icon",presets:"card_editor_presets",chip:"card_editor_chip",show_turn_off:"card_editor_show_turn_off",mushroom:"card_editor_mushroom",interactions:"card_editor_interactions",tap:"card_editor_tap",double_tap:"card_editor_double_tap",hold:"card_editor_hold",tap_action:"card_editor_tap_action",double_tap_action:"card_editor_double_tap_action",hold_action:"card_editor_hold_action"},So={popup:"card_editor_press_popup",run:"card_editor_press_run",stop:"card_editor_press_stop",run_or_stop:"card_editor_press_run_or_stop",action:"card_editor_press_action",none:"card_editor_press_none"},Co=o=>Object.hasOwn(He,o),Eo=o=>o.endsWith("_action"),ko=o=>Ut.some(t=>t===o),To={locale:{language:"en"}};function Po(){return H()??To}function Ro(o){return l({localize:o},"card_language")}function Ho(o){let t=Ro(o);return new Intl.ListFormat(t,{style:"long",type:"conjunction"}).format(X.map(e=>$({locale:{language:t}},e)))}async function Oe(){let o=H(),t=Nt.map(e=>({value:e,label:l(o,So[e])}));return{schema:[{name:"entity",required:!0,selector:{entity:{filter:{integration:"timerify",domain:"number"}}}},{name:"layout",selector:{select:{options:[{value:"pill",label:l(o,"card_editor_layout_pill")},{value:"round",label:l(o,"card_editor_layout_round")}]}}},{name:"",type:"grid",schema:[{name:"name",selector:{text:{}}},{name:"icon",selector:{icon:{}}}]},{name:"presets",selector:{select:{multiple:!0,custom_value:!0,options:X.map(e=>({value:String(e),label:$(Po(),e)}))}}},{name:"chip",selector:{number:{min:1,max:Dt,mode:"box"}}},{name:"show_turn_off",selector:{boolean:{}}},{name:"mushroom",selector:{boolean:{}}},{name:"interactions",type:"expandable",flatten:!0,icon:"mdi:gesture-tap",schema:[{name:"tap",selector:{select:{options:t}}},{name:"tap_action",selector:{ui_action:{default_action:"more-info"}}},{name:"double_tap",selector:{select:{options:t}}},{name:"double_tap_action",selector:{ui_action:{default_action:"more-info"}}},{name:"hold",selector:{select:{options:t}}},{name:"hold_action",selector:{ui_action:{default_action:"more-info"}}}]}],assertConfig:Se,computeLabel:({name:e},n)=>Co(e)?n(Lt(He[e])):"",computeHelper:({name:e},n)=>e==="presets"?l({localize:n},"card_editor_presets_helper",{presets:Ho(n)}):e==="mushroom"?Ft()?void 0:l({localize:n},"card_editor_mushroom_missing"):ko(e)?l({localize:n},"card_editor_press_helper"):Eo(e)?l({localize:n},"card_editor_action_helper"):void 0}}function Me(o,t,e){ct(o);let n=r=>{let s=o.entities[r];return s?.platform==="timerify"&&(s.translation_key==="run_for"||s.translation_key==="run_for_with_target")},i=r=>r.filter(n).sort()[0];return{entity:i(t)??i(e)??i(Object.keys(o.entities))??"",layout:"pill",presets:X.map(String)}}var Oo="not_found",Mo="timer_incomplete",zo="unauthorized";async function Le(o,t){let e=Date.now();try{let n=await o.callWS({type:"timerify/timer",entity_id:t}),i=Bt(n.server_time),r=i===void 0?0:i-(e+Date.now())/2;return{status:"found",info:n,clockOffset:r}}catch(n){let i=typeof n=="object"&&n!==null&&"code"in n?n.code:"";return i===Oo?{status:"not_found"}:i===Mo?{status:"incomplete"}:{status:i===zo?"unauthorized":"failed"}}}var Q=o=>Date.now()+(o.status==="found"?o.clockOffset:0),pt=(o,t)=>o.disabled_sensors.includes(t),N=o=>o!==void 0&&o.state!=="unavailable"&&o.state!=="unknown";function Lo(o,t){return o===void 0||o.state==="unavailable"||o.state==="unknown"?!1:t.states.includes(o.state)===(t.match==="is")}var Do="mdi:timer-outline",ze=o=>o===void 0||o.state==="unavailable";function Bt(o){let t=typeof o=="string"?Date.parse(o):Number.NaN;return Number.isNaN(t)?void 0:t}function De(o,t,e,n){let i=e.status==="found"?e.info:void 0,r=o.states[t.entity],s=i&&o.states[i.target],c=t.name||s&&o.formatEntityName(s,void 0)||r?.attributes.friendly_name||t.entity,d=t.icon?{icon:t.icon}:s?{stateObj:s}:{icon:Do},h={name:c,icon:d,target:s,remaining:0},f=i&&o.states[i.ends_at];if(i===void 0||f===void 0||ze(r)||ze(f))return{...h,state:"unavailable",progress:0};let m=Bt(f.state);if(m===void 0)return Lo(s,i.target_on)?{...h,state:"open",progress:1}:{...h,state:"idle",progress:0};if(f.attributes.limit===!0)return{...h,state:"limit",progress:1,endsAt:new Date(m)};let b=Bt(f.attributes.started_at),v=b===void 0?0:(m-b)/1e3,k=Math.max(0,(m-n)/1e3);return{...h,state:"counting",remaining:k,progress:v>0?Math.min(1,k/v):1,endsAt:new Date(m)}}var U=({state:o})=>o==="counting"||o==="limit"||o==="open",tt=({state:o})=>o==="counting"||o==="limit";function ht(o,t){return t?[o,t.ends_at,t.next_command,t.target,...t.intervals.map(({entity_id:e})=>e)]:[o]}var No=["locale","language","localize","config","user","connected","entities","formatEntityName","formatEntityState","formatEntityAttributeValue"];function mt(o,t,e){for(let i of o.keys())if(i!=="hass")return!0;let n=o.get("hass");return n===void 0||t===void 0?!0:No.some(i=>n[i]!==t[i])||e.some(i=>n.states[i]!==t.states[i])}function ft(o){return"stateObj"in o.icon?p`<ha-state-icon .stateObj=${o.icon.stateObj}></ha-state-icon>`:p`<ha-icon .icon=${o.icon.icon}></ha-icon>`}var gt=o=>o.tap==="popup"?"dialog":void 0,I=o=>o.tap!=="none"||o.double_tap!=="none"||o.hold!=="none";function _t(o,t,e,n){if(!t.show_turn_off||!U(o))return u;let i=l(e,"card_turn_off");return p`
    <button class="turn-off" type="button" aria-label=${i} title=${i} @click=${n}>
      <ha-icon class="turn-off-icon" icon="mdi:power"></ha-icon>
      <span class="turn-off-label">${i}</span>
    </button>
  `}var et={pill:245,pillWithChip:335,round:101},ot=o=>y`
  ${o} .turn-off {
    width: 40px;
    height: 40px;
    padding: 0;
    border-radius: 20px;
  }
  ${o} .turn-off-label {
    display: none;
  }
  ${o} .turn-off-icon {
    display: flex;
  }
  :host([data-mushroom]) ${o} .turn-off {
    width: calc(${a.controlHeight} * ${a.controlButtonRatio});
    height: ${a.controlHeight};
    padding: 0;
    border-radius: ${a.controlRadius};
  }
`;function Uo(o,t,e){if(o.state!=="unavailable")return o.target?e.formatEntityState(o.target):"";let n=e.states[t.entity];if(N(n))return"";let i={entity_id:t.entity,state:"unavailable",attributes:{}};return e.formatEntityState(n??i,"unavailable")}function yt(o,t,e,n){if(!tt(o)||o.endsAt===void 0)return Uo(o,t,e);let i=Z(e,o.endsAt,n);return o.state==="limit"?p`<span class="until">${l(e,"card_until_latest",{time:i})}</span>`:p`
    <span class="remaining">${D(o.remaining)}</span>
    <span class="until">${l(e,"card_until",{time:i})}</span>
  `}var Ne=y`
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
`,Ue=y`
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
`;var x=o=>o??u;var Ie={ATTRIBUTE:1,CHILD:2,PROPERTY:3,BOOLEAN_ATTRIBUTE:4,EVENT:5,ELEMENT:6},Fe=o=>(...t)=>({_$litDirective$:o,values:t}),bt=class{constructor(t){}get _$AU(){return this._$AM._$AU}_$AT(t,e,n){this._$Ct=t,this._$AM=e,this._$Ci=n}_$AS(t,e){return this.update(t,e)}update(t,e){return this.render(...e)}};var Be="important",Io=" !"+Be,je=Fe(class extends bt{constructor(o){if(super(o),o.type!==Ie.ATTRIBUTE||o.name!=="style"||o.strings?.length>2)throw Error("The `styleMap` directive must be used in the `style` attribute and must be the only part in the attribute.")}render(o){return Object.keys(o).reduce((t,e)=>{let n=o[e];return n==null?t:t+`${e=e.includes("-")?e:e.replace(/(?:^(webkit|moz|ms|o)|)(?=[A-Z])/g,"-$&").toLowerCase()}:${n};`},"")}update(o,[t]){let{style:e}=o.element;if(this.ft===void 0)return this.ft=new Set(Object.keys(t)),this.render(t);for(let n of this.ft)t[n]==null&&(this.ft.delete(n),n.includes("-")?e.removeProperty(n):e[n]=null);for(let n in t){let i=t[n];if(i!=null){this.ft.add(n);let r=typeof i=="string"&&i.endsWith(Io);n.includes("-")||r?e.setProperty(n,r?i.slice(0,-11):i,r?Be:""):e[n]=i}}return S}});function Ve(o,t,e,n,i,r,s){let c=Math.round(o.progress*1e3)/10,d=I(t);return p`
    <ha-card
      class="pill ${o.state} ${t.chip===void 0?"":"with-chip"} ${t.show_turn_off?"with-turn-off":""}"
    >
      <div
        class="body"
        role=${x(d?"button":void 0)}
        tabindex=${x(d?"0":void 0)}
        aria-haspopup=${x(gt(t))}
        aria-labelledby=${x(d?"label":void 0)}
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
          <span class="fill" style=${je({width:`${c}%`})}></span>
        </span>
      </div>
      <div class="content">
        <span class="icon">${ft(o)}</span>
        <span class="text" id="label">
          <span class="name">${o.name}</span>
          <span class="status">${yt(o,t,e,s)}</span>
        </span>
        ${_t(o,t,e,r)}
        ${t.chip===void 0?u:p`
              <button
                class="chip"
                type="button"
                aria-label=${l(e,"card_add_time",{duration:$(e,t.chip)})}
                ?disabled=${o.state==="unavailable"}
                @click=${i}
              >
                <span class="chip-text">+${$(e,t.chip)}</span>
              </button>
            `}
      </div>
    </ha-card>
  `}var We=y`
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
  @container (width < ${et.pill}px) {
    ${ot(y`.pill`)}
  }
  @container (width < ${et.pillWithChip}px) {
    ${ot(y`.pill.with-chip`)}
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
`;function Fo(o){let t=o?.attributes.max;return typeof t=="number"&&Number.isFinite(t)?t:void 0}function Bo(o,t){return t===void 0?[...o]:o.filter(e=>e<=t)}function jo(o){let t=o?.attributes.commands;return Array.isArray(t)?t.flatMap(e=>{if(typeof e!="object"||e===null)return[];let{id:n,at:i,action:r,minutes:s,settings:c}=e,d=typeof i=="string"?new Date(i):void 0;return typeof n!="string"||d===void 0||Number.isNaN(d.getTime())||r!=="on"&&r!=="off"?[]:[{id:n,at:d,action:r,minutes:typeof s=="number"&&s>0?s:null,settings:typeof c=="object"&&c!==null?Object.entries(c):[]}]}):[]}var Vo=o=>`/config/integrations/integration/timerify#config_entry=${encodeURIComponent(o)}`,vt=class extends w{static properties={hass:{attribute:!1},config:{attribute:!1},lookup:{attribute:!1},view:{attribute:!1},opened:{state:!0}};static styles=y`
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
  `;constructor(){super(),this.opened=!1}open(){this.opened=!0}close(){this.#t?.close(),this.#a()}disconnectedCallback(){super.disconnectedCallback(),this.close()}get#t(){return this.renderRoot.querySelector("dialog")}#e=()=>{this.#t?.open||this.#a()};#o=!1;#n=t=>{this.#o=t.target===t.currentTarget};#i=t=>{this.#o&&=t.target===t.currentTarget};#r=()=>{this.#o=!1};#d=t=>{let e=this.#o&&t.target===t.currentTarget;this.#o=!1,e&&this.close()};#a(){this.opened&&(this.opened=!1,this.dispatchEvent(new CustomEvent("closed")))}shouldUpdate(t){if(!this.hasUpdated||t.has("opened"))return!0;let e=ht(this.config.entity,this.lookup.info);return this.opened&&mt(t,this.hass,e)}updated(t){let e=this.#t;t.has("opened")&&this.opened&&e&&!e.open&&e.showModal()}render(){return p`
      <dialog
        aria-labelledby="title"
        @cancel=${()=>this.close()}
        @close=${this.#e}
        @pointerdown=${this.#n}
        @pointerup=${this.#i}
        @pointercancel=${this.#r}
        @click=${this.#d}
      >
        ${this.opened?this.#s():u}
      </dialog>
    `}#s(){let{hass:t,view:e}=this,n=Q(this.lookup);return p`
      <div class="wrapper">
        <header>
          <h2 id="title">${e.name}</h2>
          <button class="close" @click=${()=>this.close()}>${l(t,"card_close")}</button>
        </header>
        ${this.#u(n)} ${this.#p()} ${this.#h()} ${this.#c(n)}
        ${this.#f()}
      </div>
    `}#u(t){let{hass:e,view:n}=this;if(!tt(n)||n.endsAt===void 0)return u;let i=Z(e,n.endsAt,t);return n.state==="limit"?p`
        <p class="countdown">
          <span class="until">${l(e,"card_until_latest",{time:i})}</span>
        </p>
      `:p`
      <p class="countdown">
        <span class="remaining">${D(n.remaining)}</span>
        <span class="until">${l(e,"card_until",{time:i})}</span>
      </p>
    `}#p(){let{hass:t,config:e,view:n}=this,i=$(t,5),r=tt(n),s=U(n),c=n.state==="unavailable",d=Fo(t.states[e.entity]),h=Bo(e.presets,d);return p`
      ${h.length>0?p`
            <div class="presets">
              ${h.map(f=>p`
                  <button
                    class="action preset"
                    ?disabled=${c}
                    @click=${()=>{le(t,e.entity,f)}}
                  >
                    ${$(t,f)}
                  </button>
                `)}
            </div>
          `:d===void 0?u:p`
              <p class="note above-maximum">
                ${l(t,"card_presets_above_maximum",{maximum:$(t,d)})}
              </p>
            `}
      <div class="adjust">
        <button
          class="action step"
          aria-label=${l(t,"card_subtract_time",{duration:i})}
          ?disabled=${!r}
          @click=${()=>{G(t,e.entity,-5)}}
        >
          −${i}
        </button>
        <button
          class="action step"
          aria-label=${l(t,"card_add_time",{duration:i})}
          ?disabled=${c}
          @click=${()=>{G(t,e.entity,5)}}
        >
          +${i}
        </button>
        <button
          class="action stop"
          ?disabled=${!s}
          @click=${()=>{L(t,e.entity)}}
        >
          ${l(t,"card_stop")}
        </button>
      </div>
    `}#h(){let{intervals:t}=this.lookup.info;return t.length===0?u:p`
      <section class="schedule">
        <h3>${l(this.hass,"card_schedule")}</h3>
        <ul>
          ${t.map(e=>p`<li>${this.#l(e)}</li>`)}
        </ul>
      </section>
    `}#l({entity_id:t,title:e}){let{hass:n}=this,i=n.states[t],r=i!==void 0&&i.state!=="unavailable",s=r&&i.state==="on",c=i??{entity_id:t,state:"unavailable",attributes:{}};return p`
      <button
        class="interval"
        role="switch"
        aria-checked=${s?"true":"false"}
        ?disabled=${!r}
        @click=${()=>{ue(n,t,!s)}}
      >
        <span class="label">
          <span class="title">${e}</span>
          ${r?u:p`<span class="state">${n.formatEntityState(c,"unavailable")}</span>`}
        </span>
        <span class="track" aria-hidden="true"><span class="knob"></span></span>
      </button>
    `}#c(t){let{hass:e,config:n,view:i}=this,{info:r}=this.lookup;if(pt(r,r.next_command))return p`
        <section class="commands">
          <p class="note">${l(e,"card_commands_disabled",{sensor:r.next_command})}</p>
        </section>
      `;let s=jo(e.states[r.next_command]);if(s.length===0)return u;let c=i.state==="unavailable";return p`
      <section class="commands">
        <h3>${l(e,"card_commands")}</h3>
        <ul>
          ${s.map((d,h)=>{let f=d.settings.map(([m,b])=>Te(e,i.target,r.percent_settings,m,b));return p`
              <li>
                <div class="command" id="command-${h}">
                  <span class="what">${this.#m(d,t)}</span>
                  ${f.length===0?u:p`<span class="settings">${f.join(", ")}</span>`}
                </div>
                <button
                  class="cancel"
                  aria-label=${l(e,"card_cancel_command")}
                  aria-describedby="command-${h}"
                  ?disabled=${c}
                  @click=${()=>{pe(e,n.entity,d.id)}}
                >
                  <span aria-hidden="true">×</span>
                </button>
              </li>
            `})}
        </ul>
      </section>
    `}#m(t,e){let{hass:n}=this,i=Z(n,t.at,e);return t.action==="off"?l(n,"card_command_off",{time:i}):t.minutes===null?l(n,"card_command_on",{time:i}):l(n,"card_command_on_for",{time:i,duration:$(n,t.minutes)})}#f(){return this.hass.user?.is_admin?p`
      <footer>
        <a href=${Vo(this.lookup.info.entry_id)} @click=${this.#g}>
          ${l(this.hass,"card_settings")}
        </a>
      </footer>
    `:u}#g=t=>{!t.ctrlKey&&!t.metaKey&&!t.shiftKey&&this.close()}};var Ke="data-held",$t=class{#t;#e;#o=!1;#n;#i;#r=!1;#d=!1;#a;#s=t=>this.#l(t);constructor(t,e){this.#t=t,this.#e=e,t.addController(this)}hostDisconnected(){this.#o=!1,this.#d=!1,this.#p(),this.#c()}cancelPress(){this.#c()}binding(){return{click:t=>{if(this.#d){this.#d=!1,t.preventDefault(),t.stopPropagation();return}this.#u()},keydown:t=>{t.key==="Enter"?(t.preventDefault(),t.repeat||this.#e().tap()):t.key===" "&&(t.preventDefault(),this.#o=!0)},keyup:t=>{if(t.key!==" ")return;let e=this.#o;this.#o=!1,e&&this.#e().tap()},pointerdown:t=>this.#h(t),pointerup:t=>{if(t.pointerId!==this.#n)return;let e=this.#r;this.#c();let{hold:n}=this.#e();e&&n!==void 0&&(this.#d=!0,n())},pointercancel:t=>this.#l(t),pointerleave:t=>this.#l(t),contextmenu:t=>{this.#n!==void 0&&t.preventDefault()}}}#u(){let{tap:t,doubleTap:e}=this.#e(),n=this.#a!==void 0;this.#p(),e===void 0?t():n?e():this.#a=setTimeout(()=>{this.#a=void 0,this.#e().tap()},250)}#p(){clearTimeout(this.#a),this.#a=void 0}#h(t){this.#e().hold===void 0||!t.isPrimary||t.button!==0||(this.#d=!1,this.#c(),this.#n=t.pointerId,window.addEventListener("pointerup",this.#s),window.addEventListener("pointercancel",this.#s),this.#i=setTimeout(()=>{this.#i=void 0,this.#r=!0,this.#t.setAttribute(Ke,"")},500))}#l(t){t.pointerId===this.#n&&this.#c()}#c(){clearTimeout(this.#i),this.#i=void 0,this.#n=void 0,this.#r=!1,window.removeEventListener("pointerup",this.#s),window.removeEventListener("pointercancel",this.#s),this.#t.removeAttribute(Ke)}};var E=80,Ge=6,Vt=(E-Ge)/2,qe=2*Math.PI*Vt;function Wo(o){if(o.state!=="counting")return p`<span class="icon">${ft(o)}</span>`;let t=D(o.remaining);return p`<span class="time" aria-hidden="true">${t}</span>`}function Ye(o,t,e,n,i,r){let s=E/2,c=I(t);return p`
    <ha-card class="round ${o.state} ${t.show_turn_off?"with-turn-off":""}">
      <div
        class="body"
        role=${x(c?"button":void 0)}
        tabindex=${x(c?"0":void 0)}
        aria-haspopup=${x(gt(t))}
        aria-labelledby=${x(c?"label":void 0)}
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
          <svg class="ring" viewBox="0 0 ${E} ${E}" aria-hidden="true">
            <circle class="track" cx=${s} cy=${s} r=${Vt}></circle>
            <circle
              class="progress"
              cx=${s}
              cy=${s}
              r=${Vt}
              transform="rotate(-90 ${s} ${s})"
              stroke-dasharray=${qe}
              stroke-dashoffset=${(1-o.progress)*qe}
            ></circle>
          </svg>
          <span class="centre">
            ${Wo(o)}
          </span>
        </div>
        <span class="text" id="label">
          <span class="name">${o.name}</span>
          <span class="status">${yt(o,t,e,r)}</span>
        </span>
        ${t.show_turn_off?p`<div class="turn-off-slot">${_t(o,t,e,i)}</div>`:u}
      </div>
    </ha-card>
  `}var Xe=y`
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
    stroke-width: ${Ge};
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
  @container (width < ${et.round}px) {
    ${ot(y`.round`)}
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
   * where it has less, and the time and the icon follow it in container units. The dial is the
   * container and not .content, so that a card without the Turn off button is laid out as
   * before (see turnOffAsIcon: only a card that has the button makes .content a container).
   * All of it is one block, so that a browser that does not know container units keeps the dial
   * at 80 px: a width capped without an aspect ratio would not be a square, and a custom
   * property with cqw in it is invalid only where it is used.
   */
  @supports (width: 1cqw) {
    .dial {
      max-width: 100%;
      height: auto;
      aspect-ratio: 1;
      container-type: inline-size;
    }
    .round .time {
      font-size: min(var(--ha-font-size-l, 16px), 20cqw);
    }
    :host(:not([data-mushroom])) .round .icon {
      /* No line of text around a small symbol: the box of the icon is the symbol. */
      line-height: 0;
      --mdc-icon-size: min(32px, 40cqw);
    }
    :host([data-mushroom]) .round .time {
      font-size: min(${a.primaryFontSize}, 20cqw);
    }
    /* 45 % of the full dial, 80 px, is 36 px, the size of Mushroom's icon shape. */
    :host([data-mushroom]) .round .icon {
      width: min(${a.iconSize}, 45cqw);
      height: min(${a.iconSize}, 45cqw);
      font-size: min(${a.iconSize}, 45cqw);
    }
  }
`;var Wt="timerify-card",nt={pill:{columns:6,rows:1,min_columns:3,min_rows:1,max_rows:1},round:{columns:3,rows:2,min_columns:2,min_rows:2,max_rows:3},pillWithTurnOff:{columns:6,rows:1,min_columns:6,min_rows:1,max_rows:1},pillWithTurnOffAndChip:{columns:9,rows:1,min_columns:9,min_rows:1,max_rows:1},roundWithTurnOff:{columns:3,rows:3,min_columns:3,min_rows:3,max_rows:3}},Kt=class extends w{static properties={hass:{attribute:!1,noAccessor:!0},_config:{state:!0},_lookup:{state:!0}};static styles=[Ne,We,Xe,Ue,y`
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
    `];static getConfigForm=Oe;static getStubConfig=Me;#t;#e=new Set;#o=!1;#n=!1;#i=new $t(this,()=>this.#g());#r=this.#i.binding();#d=()=>{let{_config:t,hass:e}=this;t?.chip!==void 0&&e!==void 0&&G(e,t.entity,t.chip)};#a=()=>{let{_config:t,hass:e}=this;t!==void 0&&e!==void 0&&L(e,t.entity)};#s;#u=!1;constructor(){super(),this._lookup={status:"pending"},new lt(this,()=>this.#s?.state==="counting"?this.#s.endsAt:void 0,()=>Q(this._lookup)),new ut(this,()=>this._config?.mushroom===!0)}get hass(){return this.#t}set hass(t){let e=this.#t;this.#t=t,this.requestUpdate("hass",e),this.#p(e,t)}setConfig(t){let e=Ce(t),n=this._config?.entity!==e.entity;this._config=e,n&&(this._lookup={status:"pending"},this.#l())}getCardSize(){return this._config?.layout!=="round"?1:this._config.show_turn_off?4:3}getGridOptions(){let t=this._config;return t?.layout==="round"?t.show_turn_off?nt.roundWithTurnOff:nt.round:t?.show_turn_off?t.chip===void 0?nt.pillWithTurnOff:nt.pillWithTurnOffAndChip:nt.pill}async getUpdateComplete(){let t=await super.getUpdateComplete();for(;this.#e.size>0;)await Promise.allSettled([...this.#e]),t=await super.getUpdateComplete();return t}#p(t,e){let n=t!==void 0&&e.connected&&!t.connected;(t===void 0||t.language!==e.language||n)&&this.#h(ct(e));let i=this._config?.entity;i!==void 0&&(t===void 0||t.entities!==e.entities||n||N(e.states[i])&&!N(t.states[i]))&&this.#l()}#h(t){let e=t.finally(()=>this.#e.delete(e));this.#e.add(e)}#l(){if(this.#o){this.#n=!0;return}this.#o=!0,this.#h(this.#c())}async#c(){try{do{this.#n=!1;let t=this._config?.entity;if(this.#t===void 0||t===void 0)return;let e=await Le(this.#t,t);this.#n||(this._lookup=e)}while(this.#n)}finally{this.#o=!1}}willUpdate(){this.#u=this.shadowRoot?.activeElement?.classList.contains("turn-off")===!0}updated(){this.#u&&this.shadowRoot?.querySelector(".turn-off")===null&&this.#m()}#m(){let t=this._config;t!==void 0&&I(t)&&this.renderRoot.querySelector(".body")?.focus()}shouldUpdate(t){let e=this._lookup.status==="found"?this._lookup.info:void 0,n=this._config?ht(this._config.entity,e):[];return mt(t,this.#t,n)}get#f(){return this.renderRoot.querySelector("timerify-card-popup")}#g(){let t=this._config,e={tap:()=>this.#_("tap")};return t!==void 0&&t.double_tap!=="none"&&(e.doubleTap=()=>this.#_("double_tap")),t!==void 0&&t.hold!=="none"&&(e.hold=()=>this.#_("hold")),e}#_(t){let{_config:e,hass:n}=this;if(!(e===void 0||n===void 0))switch(e[t]){case"popup":this.#i.cancelPress(),this.#f?.open();break;case"run":zt(n,e.entity);break;case"stop":L(n,e.entity);break;case"run_or_stop":this.#y(n,e);break;case"action":this.#b(t,e);break;case"none":break}}#y(t,e){let n=this.#s;n!==void 0&&(U(n)?L(t,e.entity):n.state==="idle"&&zt(t,e.entity))}#b(t,e){if(this._lookup.status!=="found")return;let n=Object.fromEntries(It.filter(i=>e[i]!==void 0).map(i=>[i,e[i]]));this.dispatchEvent(new CustomEvent("hass-action",{detail:{config:{entity:this._lookup.info.target,...n},action:t},bubbles:!0,composed:!0}))}#v(t,e){let n=this._lookup;if(n.status==="unauthorized")return l(t,"card_not_allowed",{entity:e.entity});if(n.status==="incomplete")return l(t,"card_timer_incomplete",{entity:e.entity});if(n.status==="found"&&pt(n.info,n.info.ends_at))return l(t,"card_ends_at_disabled",{sensor:n.info.ends_at});if(n.status!=="not_found")return;let i=t.states[e.entity];return i===void 0?l(t,"card_entity_not_found",{entity:e.entity}):N(i)?l(t,"card_not_a_timer",{entity:e.entity}):void 0}render(){let t=this.#t,e=this._config;if(!t||!e)return u;let n=this.#v(t,e);if(n)return this.#s=void 0,p`
        <ha-card>
          <div class="warning" role="alert">
            <ha-icon icon="mdi:alert-outline"></ha-icon>
            <span>${n}</span>
          </div>
        </ha-card>
      `;let i=Q(this._lookup),r=De(t,e,this._lookup,i);return this.#s=r,p`
      ${e.layout==="round"?Ye(r,e,t,this.#r,this.#a,i):Ve(r,e,t,this.#r,this.#d,this.#a,i)}
      ${this._lookup.status==="found"?p`
            <timerify-card-popup
              .hass=${t}
              .config=${e}
              .lookup=${this._lookup}
              .view=${r}
              @closed=${()=>this.#m()}
            ></timerify-card-popup>
          `:u}
    `}};if(!customElements.get(Wt)){customElements.define("timerify-card-popup",vt),customElements.define(Wt,Kt);let o={type:Wt,name:"Timerify",description:l(void 0,"card_picker_description"),preview:!0,documentationURL:"https://github.com/klimofey/timerify#dashboard-card"};(window.customCards??=[]).push(o),be(()=>{o.description=l(H(),"card_picker_description")})}export{Kt as TimerifyCard};
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
