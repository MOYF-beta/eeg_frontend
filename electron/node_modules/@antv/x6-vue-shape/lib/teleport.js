"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.connect = connect;
exports.disconnect = disconnect;
exports.isActive = isActive;
exports.getTeleport = getTeleport;
const vue_demi_1 = require("vue-demi");
let active = false;
const items = (0, vue_demi_1.reactive)({});
function connect(id, component, container, node, graph) {
    if (active) {
        items[id] = (0, vue_demi_1.markRaw)((0, vue_demi_1.defineComponent)({
            render: () => (0, vue_demi_1.h)(vue_demi_1.Teleport, { to: container }, [
                (0, vue_demi_1.h)(component, { node, graph }),
            ]),
            provide: () => ({
                getNode: () => node,
                getGraph: () => graph,
            }),
        }));
    }
}
function disconnect(id) {
    if (active) {
        delete items[id];
    }
}
function isActive() {
    return active;
}
let itemComponets = null;
function getTeleport() {
    if (!vue_demi_1.isVue3) {
        throw new Error('teleport is only available in Vue3');
    }
    if (itemComponets && active) {
        return null;
    }
    active = true;
    itemComponets = (0, vue_demi_1.defineComponent)({
        setup() {
            (0, vue_demi_1.onBeforeUnmount)(() => {
                itemComponets = null;
            });
            return () => (0, vue_demi_1.h)(vue_demi_1.Fragment, {}, Object.keys(items).map((id) => (0, vue_demi_1.h)(items[id])));
        },
    });
    return itemComponets;
}
//# sourceMappingURL=teleport.js.map