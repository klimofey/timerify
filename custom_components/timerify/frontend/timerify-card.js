var nt=globalThis,it=nt.ShadowRoot&&(nt.ShadyCSS===void 0||nt.ShadyCSS.nativeShadow)&&"adoptedStyleSheets"in Document.prototype&&"replace"in CSSStyleSheet.prototype,$t=Symbol(),Kt=new WeakMap,F=class{constructor(t,e,n){if(this._$cssResult$=!0,n!==$t)throw Error("CSSResult is not constructable. Use `unsafeCSS` or `css` instead.");this.cssText=t,this.t=e}get styleSheet(){let t=this.o,e=this.t;if(it&&t===void 0){let n=e!==void 0&&e.length===1;n&&(t=Kt.get(e)),t===void 0&&((this.o=t=new CSSStyleSheet).replaceSync(this.cssText),n&&Kt.set(e,t))}return t}toString(){return this.cssText}},rt=o=>new F(typeof o=="string"?o:o+"",void 0,$t),y=(o,...t)=>{let e=o.length===1?o[0]:t.reduce((n,i,r)=>n+(s=>{if(s._$cssResult$===!0)return s.cssText;if(typeof s=="number")return s;throw Error("Value passed to 'css' function must be a 'css' function result: "+s+". Use 'unsafeCSS' to pass non-literal values, but take care to ensure page security.")})(i)+o[r+1],o[0]);return new F(e,o,$t)},qt=(o,t)=>{if(it)o.adoptedStyleSheets=t.map(e=>e instanceof CSSStyleSheet?e:e.styleSheet);else for(let e of t){let n=document.createElement("style"),i=nt.litNonce;i!==void 0&&n.setAttribute("nonce",i),n.textContent=e.cssText,o.appendChild(n)}},xt=it?o=>o:o=>o instanceof CSSStyleSheet?(t=>{let e="";for(let n of t.cssRules)e+=n.cssText;return rt(e)})(o):o;var{is:Xe,defineProperty:Ze,getOwnPropertyDescriptor:Je,getOwnPropertyNames:Qe,getOwnPropertySymbols:to,getPrototypeOf:eo}=Object,st=globalThis,Gt=st.trustedTypes,oo=Gt?Gt.emptyScript:"",no=st.reactiveElementPolyfillSupport,B=(o,t)=>o,wt={toAttribute(o,t){switch(t){case Boolean:o=o?oo:null;break;case Object:case Array:o=o==null?o:JSON.stringify(o)}return o},fromAttribute(o,t){let e=o;switch(t){case Boolean:e=o!==null;break;case Number:e=o===null?null:Number(o);break;case Object:case Array:try{e=JSON.parse(o)}catch{e=null}}return e}},Xt=(o,t)=>!Xe(o,t),Yt={attribute:!0,type:String,converter:wt,reflect:!1,useDefault:!1,hasChanged:Xt};Symbol.metadata??=Symbol("metadata"),st.litPropertyMetadata??=new WeakMap;var A=class extends HTMLElement{static addInitializer(t){this._$Ei(),(this.l??=[]).push(t)}static get observedAttributes(){return this.finalize(),this._$Eh&&[...this._$Eh.keys()]}static createProperty(t,e=Yt){if(e.state&&(e.attribute=!1),this._$Ei(),this.prototype.hasOwnProperty(t)&&((e=Object.create(e)).wrapped=!0),this.elementProperties.set(t,e),!e.noAccessor){let n=Symbol(),i=this.getPropertyDescriptor(t,n,e);i!==void 0&&Ze(this.prototype,t,i)}}static getPropertyDescriptor(t,e,n){let{get:i,set:r}=Je(this.prototype,t)??{get(){return this[e]},set(s){this[e]=s}};return{get:i,set(s){let c=i?.call(this);r?.call(this,s),this.requestUpdate(t,c,n)},configurable:!0,enumerable:!0}}static getPropertyOptions(t){return this.elementProperties.get(t)??Yt}static _$Ei(){if(this.hasOwnProperty(B("elementProperties")))return;let t=eo(this);t.finalize(),t.l!==void 0&&(this.l=[...t.l]),this.elementProperties=new Map(t.elementProperties)}static finalize(){if(this.hasOwnProperty(B("finalized")))return;if(this.finalized=!0,this._$Ei(),this.hasOwnProperty(B("properties"))){let e=this.properties,n=[...Qe(e),...to(e)];for(let i of n)this.createProperty(i,e[i])}let t=this[Symbol.metadata];if(t!==null){let e=litPropertyMetadata.get(t);if(e!==void 0)for(let[n,i]of e)this.elementProperties.set(n,i)}this._$Eh=new Map;for(let[e,n]of this.elementProperties){let i=this._$Eu(e,n);i!==void 0&&this._$Eh.set(i,e)}this.elementStyles=this.finalizeStyles(this.styles)}static finalizeStyles(t){let e=[];if(Array.isArray(t)){let n=new Set(t.flat(1/0).reverse());for(let i of n)e.unshift(xt(i))}else t!==void 0&&e.push(xt(t));return e}static _$Eu(t,e){let n=e.attribute;return n===!1?void 0:typeof n=="string"?n:typeof t=="string"?t.toLowerCase():void 0}constructor(){super(),this._$Ep=void 0,this.isUpdatePending=!1,this.hasUpdated=!1,this._$Em=null,this._$Ev()}_$Ev(){this._$ES=new Promise(t=>this.enableUpdating=t),this._$AL=new Map,this._$E_(),this.requestUpdate(),this.constructor.l?.forEach(t=>t(this))}addController(t){(this._$EO??=new Set).add(t),this.renderRoot!==void 0&&this.isConnected&&t.hostConnected?.()}removeController(t){this._$EO?.delete(t)}_$E_(){let t=new Map,e=this.constructor.elementProperties;for(let n of e.keys())this.hasOwnProperty(n)&&(t.set(n,this[n]),delete this[n]);t.size>0&&(this._$Ep=t)}createRenderRoot(){let t=this.shadowRoot??this.attachShadow(this.constructor.shadowRootOptions);return qt(t,this.constructor.elementStyles),t}connectedCallback(){this.renderRoot??=this.createRenderRoot(),this.enableUpdating(!0),this._$EO?.forEach(t=>t.hostConnected?.())}enableUpdating(t){}disconnectedCallback(){this._$EO?.forEach(t=>t.hostDisconnected?.())}attributeChangedCallback(t,e,n){this._$AK(t,n)}_$ET(t,e){let n=this.constructor.elementProperties.get(t),i=this.constructor._$Eu(t,n);if(i!==void 0&&n.reflect===!0){let r=(n.converter?.toAttribute!==void 0?n.converter:wt).toAttribute(e,n.type);this._$Em=t,r==null?this.removeAttribute(i):this.setAttribute(i,r),this._$Em=null}}_$AK(t,e){let n=this.constructor,i=n._$Eh.get(t);if(i!==void 0&&this._$Em!==i){let r=n.getPropertyOptions(i),s=typeof r.converter=="function"?{fromAttribute:r.converter}:r.converter?.fromAttribute!==void 0?r.converter:wt;this._$Em=i;let c=s.fromAttribute(e,r.type);this[i]=c??this._$Ej?.get(i)??c,this._$Em=null}}requestUpdate(t,e,n,i=!1,r){if(t!==void 0){let s=this.constructor;if(i===!1&&(r=this[t]),n??=s.getPropertyOptions(t),!((n.hasChanged??Xt)(r,e)||n.useDefault&&n.reflect&&r===this._$Ej?.get(t)&&!this.hasAttribute(s._$Eu(t,n))))return;this.C(t,e,n)}this.isUpdatePending===!1&&(this._$ES=this._$EP())}C(t,e,{useDefault:n,reflect:i,wrapped:r},s){n&&!(this._$Ej??=new Map).has(t)&&(this._$Ej.set(t,s??e??this[t]),r!==!0||s!==void 0)||(this._$AL.has(t)||(this.hasUpdated||n||(e=void 0),this._$AL.set(t,e)),i===!0&&this._$Em!==t&&(this._$Eq??=new Set).add(t))}async _$EP(){this.isUpdatePending=!0;try{await this._$ES}catch(e){Promise.reject(e)}let t=this.scheduleUpdate();return t!=null&&await t,!this.isUpdatePending}scheduleUpdate(){return this.performUpdate()}performUpdate(){if(!this.isUpdatePending)return;if(!this.hasUpdated){if(this.renderRoot??=this.createRenderRoot(),this._$Ep){for(let[i,r]of this._$Ep)this[i]=r;this._$Ep=void 0}let n=this.constructor.elementProperties;if(n.size>0)for(let[i,r]of n){let{wrapped:s}=r,c=this[i];s!==!0||this._$AL.has(i)||c===void 0||this.C(i,void 0,r,c)}}let t=!1,e=this._$AL;try{t=this.shouldUpdate(e),t?(this.willUpdate(e),this._$EO?.forEach(n=>n.hostUpdate?.()),this.update(e)):this._$EM()}catch(n){throw t=!1,this._$EM(),n}t&&this._$AE(e)}willUpdate(t){}_$AE(t){this._$EO?.forEach(e=>e.hostUpdated?.()),this.hasUpdated||(this.hasUpdated=!0,this.firstUpdated(t)),this.updated(t)}_$EM(){this._$AL=new Map,this.isUpdatePending=!1}get updateComplete(){return this.getUpdateComplete()}getUpdateComplete(){return this._$ES}shouldUpdate(t){return!0}update(t){this._$Eq&&=this._$Eq.forEach(e=>this._$ET(e,this[e])),this._$EM()}updated(t){}firstUpdated(t){}};A.elementStyles=[],A.shadowRootOptions={mode:"open"},A[B("elementProperties")]=new Map,A[B("finalized")]=new Map,no?.({ReactiveElement:A}),(st.reactiveElementVersions??=[]).push("2.1.2");var Pt=globalThis,Zt=o=>o,at=Pt.trustedTypes,Jt=at?at.createPolicy("lit-html",{createHTML:o=>o}):void 0,ie="$lit$",C=`lit$${Math.random().toFixed(9).slice(2)}$`,re="?"+C,io=`<${re}>`,R=document,V=()=>R.createComment(""),W=o=>o===null||typeof o!="object"&&typeof o!="function",Rt=Array.isArray,ro=o=>Rt(o)||typeof o?.[Symbol.iterator]=="function",At=`[ 	
\f\r]`,j=/<(?:(!--|\/[^a-zA-Z])|(\/?[a-zA-Z][^>\s]*)|(\/?$))/g,Qt=/-->/g,te=/>/g,T=RegExp(`>|${At}(?:([^\\s"'>=/]+)(${At}*=${At}*(?:[^ 	
\f\r"'\`<>=]|("|')|))|$)`,"g"),ee=/'/g,oe=/"/g,se=/^(?:script|style|textarea|title)$/i,Ht=o=>(t,...e)=>({_$litType$:o,strings:t,values:e}),p=Ht(1),Wo=Ht(2),Ko=Ht(3),S=Symbol.for("lit-noChange"),l=Symbol.for("lit-nothing"),ne=new WeakMap,P=R.createTreeWalker(R,129);function ae(o,t){if(!Rt(o)||!o.hasOwnProperty("raw"))throw Error("invalid template strings array");return Jt!==void 0?Jt.createHTML(t):t}var so=(o,t)=>{let e=o.length-1,n=[],i,r=t===2?"<svg>":t===3?"<math>":"",s=j;for(let c=0;c<e;c++){let d=o[c],f,g,h=-1,b=0;for(;b<d.length&&(s.lastIndex=b,g=s.exec(d),g!==null);)b=s.lastIndex,s===j?g[1]==="!--"?s=Qt:g[1]!==void 0?s=te:g[2]!==void 0?(se.test(g[2])&&(i=RegExp("</"+g[2],"g")),s=T):g[3]!==void 0&&(s=T):s===T?g[0]===">"?(s=i??j,h=-1):g[1]===void 0?h=-2:(h=s.lastIndex-g[2].length,f=g[1],s=g[3]===void 0?T:g[3]==='"'?oe:ee):s===oe||s===ee?s=T:s===Qt||s===te?s=j:(s=T,i=void 0);let v=s===T&&o[c+1].startsWith("/>")?" ":"";r+=s===j?d+io:h>=0?(n.push(f),d.slice(0,h)+ie+d.slice(h)+C+v):d+C+(h===-2?c:v)}return[ae(o,r+(o[e]||"<?>")+(t===2?"</svg>":t===3?"</math>":"")),n]},K=class o{constructor({strings:t,_$litType$:e},n){let i;this.parts=[];let r=0,s=0,c=t.length-1,d=this.parts,[f,g]=so(t,e);if(this.el=o.createElement(f,n),P.currentNode=this.el.content,e===2||e===3){let h=this.el.content.firstChild;h.replaceWith(...h.childNodes)}for(;(i=P.nextNode())!==null&&d.length<c;){if(i.nodeType===1){if(i.hasAttributes())for(let h of i.getAttributeNames())if(h.endsWith(ie)){let b=g[s++],v=i.getAttribute(h).split(C),k=/([.?@])?(.*)/.exec(b);d.push({type:1,index:r,name:k[2],strings:v,ctor:k[1]==="."?Ct:k[1]==="?"?Et:k[1]==="@"?kt:M}),i.removeAttribute(h)}else h.startsWith(C)&&(d.push({type:6,index:r}),i.removeAttribute(h));if(se.test(i.tagName)){let h=i.textContent.split(C),b=h.length-1;if(b>0){i.textContent=at?at.emptyScript:"";for(let v=0;v<b;v++)i.append(h[v],V()),P.nextNode(),d.push({type:2,index:++r});i.append(h[b],V())}}}else if(i.nodeType===8)if(i.data===re)d.push({type:2,index:r});else{let h=-1;for(;(h=i.data.indexOf(C,h+1))!==-1;)d.push({type:7,index:r}),h+=C.length-1}r++}}static createElement(t,e){let n=R.createElement("template");return n.innerHTML=t,n}};function O(o,t,e=o,n){if(t===S)return t;let i=n!==void 0?e._$Co?.[n]:e._$Cl,r=W(t)?void 0:t._$litDirective$;return i?.constructor!==r&&(i?._$AO?.(!1),r===void 0?i=void 0:(i=new r(o),i._$AT(o,e,n)),n!==void 0?(e._$Co??=[])[n]=i:e._$Cl=i),i!==void 0&&(t=O(o,i._$AS(o,t.values),i,n)),t}var St=class{constructor(t,e){this._$AV=[],this._$AN=void 0,this._$AD=t,this._$AM=e}get parentNode(){return this._$AM.parentNode}get _$AU(){return this._$AM._$AU}u(t){let{el:{content:e},parts:n}=this._$AD,i=(t?.creationScope??R).importNode(e,!0);P.currentNode=i;let r=P.nextNode(),s=0,c=0,d=n[0];for(;d!==void 0;){if(s===d.index){let f;d.type===2?f=new q(r,r.nextSibling,this,t):d.type===1?f=new d.ctor(r,d.name,d.strings,this,t):d.type===6&&(f=new Tt(r,this,t)),this._$AV.push(f),d=n[++c]}s!==d?.index&&(r=P.nextNode(),s++)}return P.currentNode=R,i}p(t){let e=0;for(let n of this._$AV)n!==void 0&&(n.strings!==void 0?(n._$AI(t,n,e),e+=n.strings.length-2):n._$AI(t[e])),e++}},q=class o{get _$AU(){return this._$AM?._$AU??this._$Cv}constructor(t,e,n,i){this.type=2,this._$AH=l,this._$AN=void 0,this._$AA=t,this._$AB=e,this._$AM=n,this.options=i,this._$Cv=i?.isConnected??!0}get parentNode(){let t=this._$AA.parentNode,e=this._$AM;return e!==void 0&&t?.nodeType===11&&(t=e.parentNode),t}get startNode(){return this._$AA}get endNode(){return this._$AB}_$AI(t,e=this){t=O(this,t,e),W(t)?t===l||t==null||t===""?(this._$AH!==l&&this._$AR(),this._$AH=l):t!==this._$AH&&t!==S&&this._(t):t._$litType$!==void 0?this.$(t):t.nodeType!==void 0?this.T(t):ro(t)?this.k(t):this._(t)}O(t){return this._$AA.parentNode.insertBefore(t,this._$AB)}T(t){this._$AH!==t&&(this._$AR(),this._$AH=this.O(t))}_(t){this._$AH!==l&&W(this._$AH)?this._$AA.nextSibling.data=t:this.T(R.createTextNode(t)),this._$AH=t}$(t){let{values:e,_$litType$:n}=t,i=typeof n=="number"?this._$AC(t):(n.el===void 0&&(n.el=K.createElement(ae(n.h,n.h[0]),this.options)),n);if(this._$AH?._$AD===i)this._$AH.p(e);else{let r=new St(i,this),s=r.u(this.options);r.p(e),this.T(s),this._$AH=r}}_$AC(t){let e=ne.get(t.strings);return e===void 0&&ne.set(t.strings,e=new K(t)),e}k(t){Rt(this._$AH)||(this._$AH=[],this._$AR());let e=this._$AH,n,i=0;for(let r of t)i===e.length?e.push(n=new o(this.O(V()),this.O(V()),this,this.options)):n=e[i],n._$AI(r),i++;i<e.length&&(this._$AR(n&&n._$AB.nextSibling,i),e.length=i)}_$AR(t=this._$AA.nextSibling,e){for(this._$AP?.(!1,!0,e);t!==this._$AB;){let n=Zt(t).nextSibling;Zt(t).remove(),t=n}}setConnected(t){this._$AM===void 0&&(this._$Cv=t,this._$AP?.(t))}},M=class{get tagName(){return this.element.tagName}get _$AU(){return this._$AM._$AU}constructor(t,e,n,i,r){this.type=1,this._$AH=l,this._$AN=void 0,this.element=t,this.name=e,this._$AM=i,this.options=r,n.length>2||n[0]!==""||n[1]!==""?(this._$AH=Array(n.length-1).fill(new String),this.strings=n):this._$AH=l}_$AI(t,e=this,n,i){let r=this.strings,s=!1;if(r===void 0)t=O(this,t,e,0),s=!W(t)||t!==this._$AH&&t!==S,s&&(this._$AH=t);else{let c=t,d,f;for(t=r[0],d=0;d<r.length-1;d++)f=O(this,c[n+d],e,d),f===S&&(f=this._$AH[d]),s||=!W(f)||f!==this._$AH[d],f===l?t=l:t!==l&&(t+=(f??"")+r[d+1]),this._$AH[d]=f}s&&!i&&this.j(t)}j(t){t===l?this.element.removeAttribute(this.name):this.element.setAttribute(this.name,t??"")}},Ct=class extends M{constructor(){super(...arguments),this.type=3}j(t){this.element[this.name]=t===l?void 0:t}},Et=class extends M{constructor(){super(...arguments),this.type=4}j(t){this.element.toggleAttribute(this.name,!!t&&t!==l)}},kt=class extends M{constructor(t,e,n,i,r){super(t,e,n,i,r),this.type=5}_$AI(t,e=this){if((t=O(this,t,e,0)??l)===S)return;let n=this._$AH,i=t===l&&n!==l||t.capture!==n.capture||t.once!==n.once||t.passive!==n.passive,r=t!==l&&(n===l||i);i&&this.element.removeEventListener(this.name,this,n),r&&this.element.addEventListener(this.name,this,t),this._$AH=t}handleEvent(t){typeof this._$AH=="function"?this._$AH.call(this.options?.host??this.element,t):this._$AH.handleEvent(t)}},Tt=class{constructor(t,e,n){this.element=t,this.type=6,this._$AN=void 0,this._$AM=e,this.options=n}get _$AU(){return this._$AM._$AU}_$AI(t){O(this,t)}};var ao=Pt.litHtmlPolyfillSupport;ao?.(K,q),(Pt.litHtmlVersions??=[]).push("3.3.3");var de=(o,t,e)=>{let n=e?.renderBefore??t,i=n._$litPart$;if(i===void 0){let r=e?.renderBefore??null;n._$litPart$=i=new q(t.insertBefore(V(),r),r,void 0,e??{})}return i._$AI(o),i};var Ot=globalThis,$=class extends A{constructor(){super(...arguments),this.renderOptions={host:this},this._$Do=void 0}createRenderRoot(){let t=super.createRenderRoot();return this.renderOptions.renderBefore??=t.firstChild,t}update(t){let e=this.render();this.hasUpdated||(this.renderOptions.isConnected=this.isConnected),super.update(t),this._$Do=de(e,this.renderRoot,this.renderOptions)}connectedCallback(){super.connectedCallback(),this._$Do?.setConnected(!0)}disconnectedCallback(){super.disconnectedCallback(),this._$Do?.setConnected(!1)}render(){return S}};$._$litElement$=!0,$.finalized=!0,Ot.litElementHydrateSupport?.({LitElement:$});var co=Ot.litElementPolyfillSupport;co?.({LitElement:$});(Ot.litElementVersions??=[]).push("4.2.2");async function L(o,t,e,n,i){try{await o.callService(t,e,n,{entity_id:i})}catch{}}function ce(o,t,e){return L(o,"number","set_value",{value:e},t)}function G(o,t,e){return L(o,"timerify","add_time",{minutes:e},t)}function Mt(o,t){return L(o,"timerify","run",{},t)}function z(o,t){return L(o,"timerify","stop",{},t)}function le(o,t,e){return L(o,"switch",e?"turn_on":"turn_off",{},t)}function ue(o,t,e){return L(o,"timerify","cancel_command",{command_id:e},t)}var pe={card_language:"en",card_entity_not_found:"Entity not found: {entity}",card_not_a_timer:"{entity} is not the Run for number of a Timerify timer",card_timer_incomplete:"The timer of {entity} cannot be shown: its target or one of its sensors is missing. Open the timer's page to see why.",card_not_allowed:"You are not allowed to see the timer {entity}",card_ends_at_disabled:"The Ends at sensor of this timer, {sensor}, is disabled. Enable it for the card to work",card_error_entity:"Choose the Run for number of a timer",card_error_layout:"The layout is pill or round",card_error_presets:"Presets are whole minutes from 1 to 1440",card_error_chip:"The quick chip is whole minutes from 1 to 1440",card_error_press:"Tap, double tap and hold can each be popup, run, stop, run_or_stop, action or none",card_error_action:"A Home Assistant action is a set of settings, such as action: more-info",card_error_show_turn_off:"show_turn_off is true or false",card_error_mushroom:"mushroom is true or false",card_close:"Close",card_until:"until {time}",card_add_time:"Add {duration}",card_subtract_time:"Take off {duration}",card_stop:"Stop",card_turn_off:"Turn off",card_schedule:"Schedule",card_commands:"Pending commands",card_commands_disabled:"Pending commands are hidden: the Next command sensor, {sensor}, is disabled",card_command_on:"On at {time}",card_command_on_for:"On at {time} for {duration}",card_command_off:"Off at {time}",card_cancel_command:"Cancel",card_settings:"Settings",card_picker_description:"The countdown, presets and schedule of a Timerify timer",card_editor_entity:"Timer",card_editor_layout:"Layout",card_editor_layout_pill:"Pill",card_editor_layout_round:"Round",card_editor_name:"Name",card_editor_icon:"Icon",card_editor_presets:"Duration presets (minutes)",card_editor_presets_helper:"Leave empty for {presets}",card_editor_chip:"Quick add chip (minutes, pill only)",card_editor_show_turn_off:"Show a Turn off button",card_editor_mushroom:"Mushroom style",card_editor_mushroom_missing:"Mushroom was not found. The card keeps the Home Assistant look.",card_editor_interactions:"Interactions",card_editor_tap:"Tap behavior",card_editor_double_tap:"Double tap behavior",card_editor_hold:"Hold behavior",card_editor_tap_action:"Tap action",card_editor_double_tap_action:"Double tap action",card_editor_hold_action:"Hold action",card_editor_press_popup:"Open the pop-up",card_editor_press_run:"Run for the default duration",card_editor_press_stop:"Stop",card_editor_press_run_or_stop:"Start or stop",card_editor_press_action:"Home Assistant action",card_editor_press_none:"Nothing",card_editor_action_helper:'Used when the behavior above is set to "Home Assistant action"'};var me="common",fe="timerify",lo=`component.${fe}.${me}.`;function Lt(o){return lo+o}function uo(o,t){return o.replace(/\{(\w+)\}/g,(e,n)=>String(t?.[n]??e))}function u(o,t,e){return o?.localize(Lt(t),e)||uo(pe[t],e)}var Y,he=Promise.resolve(),ge,_e=new Set;function dt(o){return o.language!==Y&&(Y=o.language,he=po(o,o.language)),he}async function po(o,t){let e;try{e=await o.loadBackendTranslation(me,fe)}catch{Y===t&&(Y=void 0);return}Y===t&&(ge={...o,localize:e},_e.forEach(n=>n()))}function H(){return ge}function ye(o){_e.add(o)}var X=[15,30,45,60,120],Ut=1440,Dt=["popup","run","stop","run_or_stop","action","none"],ho=["tap","double_tap","hold"],Nt=["tap_action","double_tap_action","hold_action"],_=class extends Error{constructor(e){super(u(H(),e));this.key=e}key};function $e(o){let t=typeof o=="number"?o:typeof o=="string"&&/^\d+$/.test(o)?Number(o):void 0;return t!==void 0&&Number.isInteger(t)&&t>=1&&t<=Ut?t:void 0}function mo(o){if(o===void 0||Array.isArray(o)&&o.length===0)return[...X];if(!Array.isArray(o))throw new _("card_error_presets");let t=new Set;for(let e of o){let n=$e(e);if(n===void 0)throw new _("card_error_presets");t.add(n)}return[...t]}function fo(o){if(o===void 0)return;let t=$e(o);if(t===void 0)throw new _("card_error_chip");return t}var xe=o=>typeof o=="object"&&o!==null?o:{},go=o=>Dt.some(t=>t===o);function zt(o,t){if(o===void 0)return t;if(!go(o))throw new _("card_error_press");return o}function be(o,t){if(o===void 0)return!1;if(typeof o!="boolean")throw new _(t);return o}var _o=o=>typeof o=="object"&&o!==null&&!Array.isArray(o);function we(o){let t={};for(let e of Nt){let n=o[e];if(n!==void 0){if(!_o(n))throw new _("card_error_action");t[e]=n}}return t}var ve=o=>typeof o=="number"||typeof o=="string";function Ae(o){let t=xe(o),{entity:e,layout:n,presets:i,chip:r}=t;if(e!==void 0&&typeof e!="string")throw new _("card_error_entity");if(n!==void 0&&typeof n!="string")throw new _("card_error_layout");if(i!==void 0&&!(Array.isArray(i)&&i.every(ve)))throw new _("card_error_presets");if(r!==void 0&&!ve(r))throw new _("card_error_chip");if(t.show_turn_off!==void 0&&typeof t.show_turn_off!="boolean")throw new _("card_error_show_turn_off");if(t.mushroom!==void 0&&typeof t.mushroom!="boolean")throw new _("card_error_mushroom");for(let s of ho)if(t[s]!==void 0&&typeof t[s]!="string")throw new _("card_error_press");we(t)}function Se(o){let t=xe(o),{entity:e,layout:n="pill",name:i,icon:r}=t;if(typeof e!="string"||!/^number\.[a-z0-9_]+$/.test(e))throw new _("card_error_entity");if(n!=="pill"&&n!=="round")throw new _("card_error_layout");let s=fo(t.chip);return{entity:e,layout:n,...typeof i=="string"&&i!==""&&{name:i},...typeof r=="string"&&r!==""&&{icon:r},presets:mo(t.presets),...s!==void 0&&{chip:s},show_turn_off:be(t.show_turn_off,"card_error_show_turn_off"),mushroom:be(t.mushroom,"card_error_mushroom"),tap:zt(t.tap,"popup"),double_tap:zt(t.double_tap,"none"),hold:zt(t.hold,n==="round"?"run_or_stop":"none"),...we(t)}}var ct=class{#t;#e;#o;#n=!1;#i;constructor(t,e,n){this.#t=t,this.#e=e,this.#o=n,t.addController(this)}hostConnected(){this.#n=!0,this.#r()}hostUpdated(){this.#r()}hostDisconnected(){this.#n=!1,this.#r()}#r(){let t=this.#e(),e=this.#n&&t!==void 0&&t.getTime()>this.#o();e&&this.#i===void 0?this.#i=setInterval(()=>this.#t.requestUpdate(),1e3):!e&&this.#i!==void 0&&(clearInterval(this.#i),this.#i=void 0)}};var Ce=o=>String(o).padStart(2,"0");function U(o){let t=Math.ceil(Math.max(0,o)),e=Math.floor(t/3600),n=Math.floor(t%3600/60),i=Ce(t%60);return e>0?`${e}:${Ce(n)}:${i}`:`${n}:${i}`}function yo({language:o,time_format:t}){if(t==="12"||t==="24")return t==="12";let e=new Intl.DateTimeFormat(t==="language"?o:void 0,{hour:"numeric"}).resolvedOptions();return e.hourCycle==="h11"||e.hourCycle==="h12"}var bo=864e5;function Ee(o,t){let e=new Intl.DateTimeFormat("en-US",{timeZone:o,year:"numeric",month:"numeric",day:"numeric"}).formatToParts(t),n=i=>Number(e.find(r=>r.type===i)?.value);return Date.UTC(n("year"),n("month")-1,n("day"))/bo}function Z(o,t,e){let{locale:n}=o,i=n.time_zone==="server"?o.config.time_zone:void 0,r=Ee(i,t.getTime())-Ee(i,e),s=r===0?{}:r>=1&&r<=6?{weekday:"short"}:{month:"short",day:"numeric"};return new Intl.DateTimeFormat(n.language,{...s,hour:"numeric",minute:"2-digit",hourCycle:yo(n)?"h12":"h23",timeZone:i}).format(t)}function x(o,t){let e=(s,c)=>new Intl.NumberFormat(o.locale.language,{style:"unit",unit:c,unitDisplay:"short",useGrouping:!1}).format(s),n=Math.floor(t/60),i=t%60,r=n>0?[e(n,"hour")]:[];return(i>0||n===0)&&r.push(e(i,"minute")),r.join(" ")}function ke(o,t,e,n,i){return e.includes(n)&&typeof i=="number"?new Intl.NumberFormat(o.locale.language,{style:"percent",maximumFractionDigits:1}).format(i/100):t===void 0?String(i):n==="hvac_mode"?o.formatEntityState(t,String(i)):o.formatEntityAttributeValue(t,n,i)}var Pe="mushroom-entity-card",vo="data-mushroom",m=(o,t)=>rt(`var(--mush-${o}, ${t})`),a={spacing:m("spacing","10px"),iconSize:m("icon-size","36px"),iconRadius:m("icon-border-radius","50%"),iconSymbolSize:m("icon-symbol-size","0.667em"),primaryColor:m("card-primary-color","var(--primary-text-color)"),primaryFontSize:m("card-primary-font-size","14px"),primaryFontWeight:m("card-primary-font-weight","500"),primaryLineHeight:m("card-primary-line-height","20px"),primaryLetterSpacing:m("card-primary-letter-spacing","0.1px"),secondaryColor:m("card-secondary-color","var(--primary-text-color)"),secondaryFontSize:m("card-secondary-font-size","12px"),secondaryFontWeight:m("card-secondary-font-weight","400"),secondaryLineHeight:m("card-secondary-line-height","16px"),secondaryLetterSpacing:m("card-secondary-letter-spacing","0.4px"),controlHeight:m("control-height","42px"),controlRadius:m("control-border-radius","12px"),controlButtonRatio:m("control-button-ratio","1"),controlIconSize:m("control-icon-size","0.5em"),controlSpacing:m("control-spacing","12px"),chipHeight:m("chip-height","36px"),chipRadius:m("chip-border-radius","19px"),chipPadding:m("chip-padding","0 0.25em"),chipFontSize:m("chip-font-size","0.3em"),chipFontWeight:m("chip-font-weight","bold"),chipBorderWidth:m("chip-border-width","var(--ha-card-border-width, 1px)"),chipBorderColor:m("chip-border-color","var(--ha-card-border-color, var(--divider-color, #e0e0e0))"),chipBoxShadow:m("chip-box-shadow","var(--ha-card-box-shadow, none)"),chipBackground:m("chip-background","var(--ha-card-background, var(--card-background-color, white))"),activeRgb:m("rgb-state-entity","var(--mush-rgb-blue, 33, 150, 243)"),disabledRgb:m("rgb-disabled","var(--rgb-disabled-text-color, 189, 189, 189)")},It=()=>customElements.get(Pe)!==void 0,J=new Set,Te=!1;function $o(o){J.add(o),!Te&&(Te=!0,customElements.whenDefined(Pe).then(()=>{for(let t of J)t.requestUpdate();J.clear()}))}var lt=class{#t;#e;constructor(t,e){this.#t=t,this.#e=e,t.addController(this)}hostConnected(){this.#o()}hostUpdate(){this.#o()}hostDisconnected(){J.delete(this.#t)}#o(){let t=this.#e(),e=It();this.#t.toggleAttribute(vo,t&&e),t&&!e&&this.#t.isConnected?$o(this.#t):J.delete(this.#t)}};var Re={entity:"card_editor_entity",layout:"card_editor_layout",name:"card_editor_name",icon:"card_editor_icon",presets:"card_editor_presets",chip:"card_editor_chip",show_turn_off:"card_editor_show_turn_off",mushroom:"card_editor_mushroom",interactions:"card_editor_interactions",tap:"card_editor_tap",double_tap:"card_editor_double_tap",hold:"card_editor_hold",tap_action:"card_editor_tap_action",double_tap_action:"card_editor_double_tap_action",hold_action:"card_editor_hold_action"},xo={popup:"card_editor_press_popup",run:"card_editor_press_run",stop:"card_editor_press_stop",run_or_stop:"card_editor_press_run_or_stop",action:"card_editor_press_action",none:"card_editor_press_none"},wo=o=>Object.hasOwn(Re,o),Ao=o=>o.endsWith("_action"),So={locale:{language:"en"}};function Co(){return H()??So}function Eo(o){return u({localize:o},"card_language")}function ko(o){let t=Eo(o);return new Intl.ListFormat(t,{style:"long",type:"conjunction"}).format(X.map(e=>x({locale:{language:t}},e)))}async function He(){let o=H(),t=Dt.map(e=>({value:e,label:u(o,xo[e])}));return{schema:[{name:"entity",required:!0,selector:{entity:{filter:{integration:"timerify",domain:"number"}}}},{name:"layout",selector:{select:{options:[{value:"pill",label:u(o,"card_editor_layout_pill")},{value:"round",label:u(o,"card_editor_layout_round")}]}}},{name:"",type:"grid",schema:[{name:"name",selector:{text:{}}},{name:"icon",selector:{icon:{}}}]},{name:"presets",selector:{select:{multiple:!0,custom_value:!0,options:X.map(e=>({value:String(e),label:x(Co(),e)}))}}},{name:"chip",selector:{number:{min:1,max:Ut,mode:"box"}}},{name:"show_turn_off",selector:{boolean:{}}},{name:"mushroom",selector:{boolean:{}}},{name:"interactions",type:"expandable",flatten:!0,icon:"mdi:gesture-tap",schema:[{name:"tap",selector:{select:{options:t}}},{name:"tap_action",selector:{ui_action:{default_action:"more-info"}}},{name:"double_tap",selector:{select:{options:t}}},{name:"double_tap_action",selector:{ui_action:{default_action:"more-info"}}},{name:"hold",selector:{select:{options:t}}},{name:"hold_action",selector:{ui_action:{default_action:"more-info"}}}]}],assertConfig:Ae,computeLabel:({name:e},n)=>wo(e)?n(Lt(Re[e])):"",computeHelper:({name:e},n)=>e==="presets"?u({localize:n},"card_editor_presets_helper",{presets:ko(n)}):e==="mushroom"?It()?void 0:u({localize:n},"card_editor_mushroom_missing"):Ao(e)?u({localize:n},"card_editor_action_helper"):void 0}}function Oe(o,t,e){dt(o);let n=r=>{let s=o.entities[r];return s?.platform==="timerify"&&s.translation_key==="run_for"},i=r=>r.filter(n).sort()[0];return{entity:i(t)??i(e)??i(Object.keys(o.entities))??"",layout:"pill",presets:X.map(String)}}var To="not_found",Po="timer_incomplete",Ro="unauthorized";async function Le(o,t){let e=Date.now();try{let n=await o.callWS({type:"timerify/timer",entity_id:t}),i=Ft(n.server_time),r=i===void 0?0:i-(e+Date.now())/2;return{status:"found",info:n,clockOffset:r}}catch(n){let i=typeof n=="object"&&n!==null&&"code"in n?n.code:"";return i===To?{status:"not_found"}:i===Po?{status:"incomplete"}:{status:i===Ro?"unauthorized":"failed"}}}var Q=o=>Date.now()+(o.status==="found"?o.clockOffset:0),ut=(o,t)=>o.disabled_sensors.includes(t),D=o=>o!==void 0&&o.state!=="unavailable"&&o.state!=="unknown";function Ho(o,t){return o===void 0||o.state==="unavailable"||o.state==="unknown"?!1:t.states.includes(o.state)===(t.match==="is")}var Oo="mdi:timer-outline",Me=o=>o===void 0||o.state==="unavailable";function Ft(o){let t=typeof o=="string"?Date.parse(o):Number.NaN;return Number.isNaN(t)?void 0:t}function ze(o,t,e,n){let i=e.status==="found"?e.info:void 0,r=o.states[t.entity],s=i&&o.states[i.target],c=t.name||s&&o.formatEntityName(s,void 0)||r?.attributes.friendly_name||t.entity,d=t.icon?{icon:t.icon}:s?{stateObj:s}:{icon:Oo},f={name:c,icon:d,target:s,remaining:0},g=i&&o.states[i.ends_at];if(i===void 0||g===void 0||Me(r)||Me(g))return{...f,state:"unavailable",progress:0};let h=Ft(g.state);if(h===void 0)return Ho(s,i.target_on)?{...f,state:"open",progress:1}:{...f,state:"idle",progress:0};let b=Ft(g.attributes.started_at),v=b===void 0?0:(h-b)/1e3,k=Math.max(0,(h-n)/1e3);return{...f,state:"counting",remaining:k,progress:v>0?Math.min(1,k/v):1,endsAt:new Date(h)}}var N=({state:o})=>o==="counting"||o==="open";function pt(o,t){return t?[o,t.ends_at,t.next_command,t.target,...t.intervals.map(({entity_id:e})=>e)]:[o]}var Mo=["locale","language","localize","config","user","connected","entities","formatEntityName","formatEntityState","formatEntityAttributeValue"];function ht(o,t,e){for(let i of o.keys())if(i!=="hass")return!0;let n=o.get("hass");return n===void 0||t===void 0?!0:Mo.some(i=>n[i]!==t[i])||e.some(i=>n.states[i]!==t.states[i])}function mt(o){return"stateObj"in o.icon?p`<ha-state-icon .stateObj=${o.icon.stateObj}></ha-state-icon>`:p`<ha-icon .icon=${o.icon.icon}></ha-icon>`}var ft=o=>o.tap==="popup"?"dialog":void 0,I=o=>o.tap!=="none"||o.double_tap!=="none"||o.hold!=="none";function gt(o,t,e,n){if(!t.show_turn_off||!N(o))return l;let i=u(e,"card_turn_off");return p`
    <button class="turn-off" type="button" aria-label=${i} title=${i} @click=${n}>
      <ha-icon class="turn-off-icon" icon="mdi:power"></ha-icon>
      <span class="turn-off-label">${i}</span>
    </button>
  `}var tt={pill:245,pillWithChip:335,round:101},et=o=>y`
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
`;function Lo(o,t,e){if(o.state!=="unavailable")return o.target?e.formatEntityState(o.target):"";let n=e.states[t.entity];if(D(n))return"";let i={entity_id:t.entity,state:"unavailable",attributes:{}};return e.formatEntityState(n??i,"unavailable")}function _t(o,t,e,n){if(o.state!=="counting"||o.endsAt===void 0)return Lo(o,t,e);let i=Z(e,o.endsAt,n);return p`
    <span class="remaining">${U(o.remaining)}</span>
    <span class="until">${u(e,"card_until",{time:i})}</span>
  `}var Ue=y`
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
`,De=y`
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
`;var w=o=>o??l;var Ne={ATTRIBUTE:1,CHILD:2,PROPERTY:3,BOOLEAN_ATTRIBUTE:4,EVENT:5,ELEMENT:6},Ie=o=>(...t)=>({_$litDirective$:o,values:t}),yt=class{constructor(t){}get _$AU(){return this._$AM._$AU}_$AT(t,e,n){this._$Ct=t,this._$AM=e,this._$Ci=n}_$AS(t,e){return this.update(t,e)}update(t,e){return this.render(...e)}};var Fe="important",zo=" !"+Fe,Be=Ie(class extends yt{constructor(o){if(super(o),o.type!==Ne.ATTRIBUTE||o.name!=="style"||o.strings?.length>2)throw Error("The `styleMap` directive must be used in the `style` attribute and must be the only part in the attribute.")}render(o){return Object.keys(o).reduce((t,e)=>{let n=o[e];return n==null?t:t+`${e=e.includes("-")?e:e.replace(/(?:^(webkit|moz|ms|o)|)(?=[A-Z])/g,"-$&").toLowerCase()}:${n};`},"")}update(o,[t]){let{style:e}=o.element;if(this.ft===void 0)return this.ft=new Set(Object.keys(t)),this.render(t);for(let n of this.ft)t[n]==null&&(this.ft.delete(n),n.includes("-")?e.removeProperty(n):e[n]=null);for(let n in t){let i=t[n];if(i!=null){this.ft.add(n);let r=typeof i=="string"&&i.endsWith(zo);n.includes("-")||r?e.setProperty(n,r?i.slice(0,-11):i,r?Fe:""):e[n]=i}}return S}});function je(o,t,e,n,i,r,s){let c=Math.round(o.progress*1e3)/10,d=I(t);return p`
    <ha-card
      class="pill ${o.state} ${t.chip===void 0?"":"with-chip"} ${t.show_turn_off?"with-turn-off":""}"
    >
      <div
        class="body"
        role=${w(d?"button":void 0)}
        tabindex=${w(d?"0":void 0)}
        aria-haspopup=${w(ft(t))}
        aria-labelledby=${w(d?"label":void 0)}
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
          <span class="fill" style=${Be({width:`${c}%`})}></span>
        </span>
      </div>
      <div class="content">
        <span class="icon">${mt(o)}</span>
        <span class="text" id="label">
          <span class="name">${o.name}</span>
          <span class="status">${_t(o,t,e,s)}</span>
        </span>
        ${gt(o,t,e,r)}
        ${t.chip===void 0?l:p`
              <button
                class="chip"
                type="button"
                aria-label=${u(e,"card_add_time",{duration:x(e,t.chip)})}
                ?disabled=${o.state==="unavailable"}
                @click=${i}
              >
                <span class="chip-text">+${x(e,t.chip)}</span>
              </button>
            `}
      </div>
    </ha-card>
  `}var Ve=y`
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
  @container (width < ${tt.pill}px) {
    ${et(y`.pill`)}
  }
  @container (width < ${tt.pillWithChip}px) {
    ${et(y`.pill.with-chip`)}
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
`;function Uo(o,t){let e=t?.attributes.max;return typeof e=="number"&&Number.isFinite(e)?o.filter(n=>n<=e):[...o]}function Do(o){let t=o?.attributes.commands;return Array.isArray(t)?t.flatMap(e=>{if(typeof e!="object"||e===null)return[];let{id:n,at:i,action:r,minutes:s,settings:c}=e,d=typeof i=="string"?new Date(i):void 0;return typeof n!="string"||d===void 0||Number.isNaN(d.getTime())||r!=="on"&&r!=="off"?[]:[{id:n,at:d,action:r,minutes:typeof s=="number"&&s>0?s:null,settings:typeof c=="object"&&c!==null?Object.entries(c):[]}]}):[]}var No=o=>`/config/integrations/integration/timerify#config_entry=${encodeURIComponent(o)}`,bt=class extends ${static properties={hass:{attribute:!1},config:{attribute:!1},lookup:{attribute:!1},view:{attribute:!1},opened:{state:!0}};static styles=y`
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
  `;constructor(){super(),this.opened=!1}open(){this.opened=!0}close(){this.#t?.close(),this.#s()}disconnectedCallback(){super.disconnectedCallback(),this.close()}get#t(){return this.renderRoot.querySelector("dialog")}#e=()=>{this.#t?.open||this.#s()};#o=!1;#n=t=>{this.#o=t.target===t.currentTarget};#i=t=>{this.#o&&=t.target===t.currentTarget};#r=()=>{this.#o=!1};#d=t=>{let e=this.#o&&t.target===t.currentTarget;this.#o=!1,e&&this.close()};#s(){this.opened&&(this.opened=!1,this.dispatchEvent(new CustomEvent("closed")))}shouldUpdate(t){if(!this.hasUpdated||t.has("opened"))return!0;let e=pt(this.config.entity,this.lookup.info);return this.opened&&ht(t,this.hass,e)}updated(t){let e=this.#t;t.has("opened")&&this.opened&&e&&!e.open&&e.showModal()}render(){return p`
      <dialog
        aria-labelledby="title"
        @cancel=${()=>this.close()}
        @close=${this.#e}
        @pointerdown=${this.#n}
        @pointerup=${this.#i}
        @pointercancel=${this.#r}
        @click=${this.#d}
      >
        ${this.opened?this.#a():l}
      </dialog>
    `}#a(){let{hass:t,view:e}=this,n=Q(this.lookup);return p`
      <div class="wrapper">
        <header>
          <h2 id="title">${e.name}</h2>
          <button class="close" @click=${()=>this.close()}>${u(t,"card_close")}</button>
        </header>
        ${this.#u(n)} ${this.#p()} ${this.#h()} ${this.#c(n)}
        ${this.#f()}
      </div>
    `}#u(t){let{hass:e,view:n}=this;if(n.state!=="counting"||n.endsAt===void 0)return l;let i=Z(e,n.endsAt,t);return p`
      <p class="countdown">
        <span class="remaining">${U(n.remaining)}</span>
        <span class="until">${u(e,"card_until",{time:i})}</span>
      </p>
    `}#p(){let{hass:t,config:e,view:n}=this,i=x(t,5),r=n.state==="counting",s=N(n),c=n.state==="unavailable",d=Uo(e.presets,t.states[e.entity]);return p`
      ${d.length===0?l:p`
            <div class="presets">
              ${d.map(f=>p`
                  <button
                    class="action preset"
                    ?disabled=${c}
                    @click=${()=>{ce(t,e.entity,f)}}
                  >
                    ${x(t,f)}
                  </button>
                `)}
            </div>
          `}
      <div class="adjust">
        <button
          class="action step"
          aria-label=${u(t,"card_subtract_time",{duration:i})}
          ?disabled=${!r}
          @click=${()=>{G(t,e.entity,-5)}}
        >
          −${i}
        </button>
        <button
          class="action step"
          aria-label=${u(t,"card_add_time",{duration:i})}
          ?disabled=${c}
          @click=${()=>{G(t,e.entity,5)}}
        >
          +${i}
        </button>
        <button
          class="action stop"
          ?disabled=${!s}
          @click=${()=>{z(t,e.entity)}}
        >
          ${u(t,"card_stop")}
        </button>
      </div>
    `}#h(){let{intervals:t}=this.lookup.info;return t.length===0?l:p`
      <section class="schedule">
        <h3>${u(this.hass,"card_schedule")}</h3>
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
        @click=${()=>{le(n,t,!s)}}
      >
        <span class="label">
          <span class="title">${e}</span>
          ${r?l:p`<span class="state">${n.formatEntityState(c,"unavailable")}</span>`}
        </span>
        <span class="track" aria-hidden="true"><span class="knob"></span></span>
      </button>
    `}#c(t){let{hass:e,config:n,view:i}=this,{info:r}=this.lookup;if(ut(r,r.next_command))return p`
        <section class="commands">
          <p class="note">${u(e,"card_commands_disabled",{sensor:r.next_command})}</p>
        </section>
      `;let s=Do(e.states[r.next_command]);if(s.length===0)return l;let c=i.state==="unavailable";return p`
      <section class="commands">
        <h3>${u(e,"card_commands")}</h3>
        <ul>
          ${s.map((d,f)=>{let g=d.settings.map(([h,b])=>ke(e,i.target,r.percent_settings,h,b));return p`
              <li>
                <div class="command" id="command-${f}">
                  <span class="what">${this.#m(d,t)}</span>
                  ${g.length===0?l:p`<span class="settings">${g.join(", ")}</span>`}
                </div>
                <button
                  class="cancel"
                  aria-label=${u(e,"card_cancel_command")}
                  aria-describedby="command-${f}"
                  ?disabled=${c}
                  @click=${()=>{ue(e,n.entity,d.id)}}
                >
                  <span aria-hidden="true">×</span>
                </button>
              </li>
            `})}
        </ul>
      </section>
    `}#m(t,e){let{hass:n}=this,i=Z(n,t.at,e);return t.action==="off"?u(n,"card_command_off",{time:i}):t.minutes===null?u(n,"card_command_on",{time:i}):u(n,"card_command_on_for",{time:i,duration:x(n,t.minutes)})}#f(){return this.hass.user?.is_admin?p`
      <footer>
        <a href=${No(this.lookup.info.entry_id)} @click=${this.#g}>
          ${u(this.hass,"card_settings")}
        </a>
      </footer>
    `:l}#g=t=>{!t.ctrlKey&&!t.metaKey&&!t.shiftKey&&this.close()}};var We="data-held",vt=class{#t;#e;#o=!1;#n;#i;#r=!1;#d=!1;#s;#a=t=>this.#l(t);constructor(t,e){this.#t=t,this.#e=e,t.addController(this)}hostDisconnected(){this.#o=!1,this.#d=!1,this.#p(),this.#c()}cancelPress(){this.#c()}binding(){return{click:t=>{if(this.#d){this.#d=!1,t.preventDefault(),t.stopPropagation();return}this.#u()},keydown:t=>{t.key==="Enter"?(t.preventDefault(),t.repeat||this.#e().tap()):t.key===" "&&(t.preventDefault(),this.#o=!0)},keyup:t=>{if(t.key!==" ")return;let e=this.#o;this.#o=!1,e&&this.#e().tap()},pointerdown:t=>this.#h(t),pointerup:t=>{if(t.pointerId!==this.#n)return;let e=this.#r;this.#c();let{hold:n}=this.#e();e&&n!==void 0&&(this.#d=!0,n())},pointercancel:t=>this.#l(t),pointerleave:t=>this.#l(t),contextmenu:t=>{this.#n!==void 0&&t.preventDefault()}}}#u(){let{tap:t,doubleTap:e}=this.#e(),n=this.#s!==void 0;this.#p(),e===void 0?t():n?e():this.#s=setTimeout(()=>{this.#s=void 0,this.#e().tap()},250)}#p(){clearTimeout(this.#s),this.#s=void 0}#h(t){this.#e().hold===void 0||!t.isPrimary||t.button!==0||(this.#d=!1,this.#c(),this.#n=t.pointerId,window.addEventListener("pointerup",this.#a),window.addEventListener("pointercancel",this.#a),this.#i=setTimeout(()=>{this.#i=void 0,this.#r=!0,this.#t.setAttribute(We,"")},500))}#l(t){t.pointerId===this.#n&&this.#c()}#c(){clearTimeout(this.#i),this.#i=void 0,this.#n=void 0,this.#r=!1,window.removeEventListener("pointerup",this.#a),window.removeEventListener("pointercancel",this.#a),this.#t.removeAttribute(We)}};var E=80,qe=6,jt=(E-qe)/2,Ke=2*Math.PI*jt;function Io(o){if(o.state!=="counting")return p`<span class="icon">${mt(o)}</span>`;let t=U(o.remaining);return p`<span class="time" aria-hidden="true">${t}</span>`}function Ge(o,t,e,n,i,r){let s=E/2,c=I(t);return p`
    <ha-card class="round ${o.state} ${t.show_turn_off?"with-turn-off":""}">
      <div
        class="body"
        role=${w(c?"button":void 0)}
        tabindex=${w(c?"0":void 0)}
        aria-haspopup=${w(ft(t))}
        aria-labelledby=${w(c?"label":void 0)}
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
            <circle class="track" cx=${s} cy=${s} r=${jt}></circle>
            <circle
              class="progress"
              cx=${s}
              cy=${s}
              r=${jt}
              transform="rotate(-90 ${s} ${s})"
              stroke-dasharray=${Ke}
              stroke-dashoffset=${(1-o.progress)*Ke}
            ></circle>
          </svg>
          <span class="centre">
            ${Io(o)}
          </span>
        </div>
        <span class="text" id="label">
          <span class="name">${o.name}</span>
          <span class="status">${_t(o,t,e,r)}</span>
        </span>
        ${t.show_turn_off?p`<div class="turn-off-slot">${gt(o,t,e,i)}</div>`:l}
      </div>
    </ha-card>
  `}var Ye=y`
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
    stroke-width: ${qe};
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
  @container (width < ${tt.round}px) {
    ${et(y`.round`)}
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
`;var Vt="timerify-card",ot={pill:{columns:6,rows:1,min_columns:3,min_rows:1,max_rows:1},round:{columns:3,rows:2,min_columns:2,min_rows:2,max_rows:3},pillWithTurnOff:{columns:6,rows:1,min_columns:6,min_rows:1,max_rows:1},pillWithTurnOffAndChip:{columns:9,rows:1,min_columns:9,min_rows:1,max_rows:1},roundWithTurnOff:{columns:3,rows:3,min_columns:3,min_rows:3,max_rows:3}},Wt=class extends ${static properties={hass:{attribute:!1,noAccessor:!0},_config:{state:!0},_lookup:{state:!0}};static styles=[Ue,Ve,Ye,De,y`
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
    `];static getConfigForm=He;static getStubConfig=Oe;#t;#e=new Set;#o=!1;#n=!1;#i=new vt(this,()=>this.#g());#r=this.#i.binding();#d=()=>{let{_config:t,hass:e}=this;t?.chip!==void 0&&e!==void 0&&G(e,t.entity,t.chip)};#s=()=>{let{_config:t,hass:e}=this;t!==void 0&&e!==void 0&&z(e,t.entity)};#a;#u=!1;constructor(){super(),this._lookup={status:"pending"},new ct(this,()=>this.#a?.endsAt,()=>Q(this._lookup)),new lt(this,()=>this._config?.mushroom===!0)}get hass(){return this.#t}set hass(t){let e=this.#t;this.#t=t,this.requestUpdate("hass",e),this.#p(e,t)}setConfig(t){let e=Se(t),n=this._config?.entity!==e.entity;this._config=e,n&&(this._lookup={status:"pending"},this.#l())}getCardSize(){return this._config?.layout!=="round"?1:this._config.show_turn_off?4:3}getGridOptions(){let t=this._config;return t?.layout==="round"?t.show_turn_off?ot.roundWithTurnOff:ot.round:t?.show_turn_off?t.chip===void 0?ot.pillWithTurnOff:ot.pillWithTurnOffAndChip:ot.pill}async getUpdateComplete(){let t=await super.getUpdateComplete();for(;this.#e.size>0;)await Promise.allSettled([...this.#e]),t=await super.getUpdateComplete();return t}#p(t,e){let n=t!==void 0&&e.connected&&!t.connected;(t===void 0||t.language!==e.language||n)&&this.#h(dt(e));let i=this._config?.entity;i!==void 0&&(t===void 0||t.entities!==e.entities||n||D(e.states[i])&&!D(t.states[i]))&&this.#l()}#h(t){let e=t.finally(()=>this.#e.delete(e));this.#e.add(e)}#l(){if(this.#o){this.#n=!0;return}this.#o=!0,this.#h(this.#c())}async#c(){try{do{this.#n=!1;let t=this._config?.entity;if(this.#t===void 0||t===void 0)return;let e=await Le(this.#t,t);this.#n||(this._lookup=e)}while(this.#n)}finally{this.#o=!1}}willUpdate(){this.#u=this.shadowRoot?.activeElement?.classList.contains("turn-off")===!0}updated(){this.#u&&this.shadowRoot?.querySelector(".turn-off")===null&&this.#m()}#m(){let t=this._config;t!==void 0&&I(t)&&this.renderRoot.querySelector(".body")?.focus()}shouldUpdate(t){let e=this._lookup.status==="found"?this._lookup.info:void 0,n=this._config?pt(this._config.entity,e):[];return ht(t,this.#t,n)}get#f(){return this.renderRoot.querySelector("timerify-card-popup")}#g(){let t=this._config,e={tap:()=>this.#_("tap")};return t!==void 0&&t.double_tap!=="none"&&(e.doubleTap=()=>this.#_("double_tap")),t!==void 0&&t.hold!=="none"&&(e.hold=()=>this.#_("hold")),e}#_(t){let{_config:e,hass:n}=this;if(!(e===void 0||n===void 0))switch(e[t]){case"popup":this.#i.cancelPress(),this.#f?.open();break;case"run":Mt(n,e.entity);break;case"stop":z(n,e.entity);break;case"run_or_stop":this.#y(n,e);break;case"action":this.#b(t,e);break;case"none":break}}#y(t,e){let n=this.#a;n!==void 0&&(N(n)?z(t,e.entity):n.state==="idle"&&Mt(t,e.entity))}#b(t,e){if(this._lookup.status!=="found")return;let n=Object.fromEntries(Nt.filter(i=>e[i]!==void 0).map(i=>[i,e[i]]));this.dispatchEvent(new CustomEvent("hass-action",{detail:{config:{entity:this._lookup.info.target,...n},action:t},bubbles:!0,composed:!0}))}#v(t,e){let n=this._lookup;if(n.status==="unauthorized")return u(t,"card_not_allowed",{entity:e.entity});if(n.status==="incomplete")return u(t,"card_timer_incomplete",{entity:e.entity});if(n.status==="found"&&ut(n.info,n.info.ends_at))return u(t,"card_ends_at_disabled",{sensor:n.info.ends_at});if(n.status!=="not_found")return;let i=t.states[e.entity];return i===void 0?u(t,"card_entity_not_found",{entity:e.entity}):D(i)?u(t,"card_not_a_timer",{entity:e.entity}):void 0}render(){let t=this.#t,e=this._config;if(!t||!e)return l;let n=this.#v(t,e);if(n)return this.#a=void 0,p`
        <ha-card>
          <div class="warning" role="alert">
            <ha-icon icon="mdi:alert-outline"></ha-icon>
            <span>${n}</span>
          </div>
        </ha-card>
      `;let i=Q(this._lookup),r=ze(t,e,this._lookup,i);return this.#a=r,p`
      ${e.layout==="round"?Ge(r,e,t,this.#r,this.#s,i):je(r,e,t,this.#r,this.#d,this.#s,i)}
      ${this._lookup.status==="found"?p`
            <timerify-card-popup
              .hass=${t}
              .config=${e}
              .lookup=${this._lookup}
              .view=${r}
              @closed=${()=>this.#m()}
            ></timerify-card-popup>
          `:l}
    `}};if(!customElements.get(Vt)){customElements.define("timerify-card-popup",bt),customElements.define(Vt,Wt);let o={type:Vt,name:"Timerify",description:u(void 0,"card_picker_description"),preview:!0,documentationURL:"https://github.com/klimofey/timerify#dashboard-card"};(window.customCards??=[]).push(o),ye(()=>{o.description=u(H(),"card_picker_description")})}export{Wt as TimerifyCard};
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
