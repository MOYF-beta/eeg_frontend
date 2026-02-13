import { defineComponent, h, reactive, isVue3, Teleport, markRaw, Fragment, onBeforeUnmount, } from 'vue-demi';
let active = false;
const items = reactive({});
export function connect(id, component, container, node, graph) {
    if (active) {
        items[id] = markRaw(defineComponent({
            render: () => h(Teleport, { to: container }, [
                h(component, { node, graph }),
            ]),
            provide: () => ({
                getNode: () => node,
                getGraph: () => graph,
            }),
        }));
    }
}
export function disconnect(id) {
    if (active) {
        delete items[id];
    }
}
export function isActive() {
    return active;
}
let itemComponets = null;
export function getTeleport() {
    if (!isVue3) {
        throw new Error('teleport is only available in Vue3');
    }
    if (itemComponets && active) {
        return null;
    }
    active = true;
    itemComponets = defineComponent({
        setup() {
            onBeforeUnmount(() => {
                itemComponets = null;
            });
            return () => h(Fragment, {}, Object.keys(items).map((id) => h(items[id])));
        },
    });
    return itemComponets;
}
//# sourceMappingURL=teleport.js.map