"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const x6_1 = require("@antv/x6");
function getMarkup(primer) {
    const content = x6_1.Markup.getForeignObjectMarkup();
    if (primer) {
        return [
            {
                tagName: primer,
                selector: 'body',
            },
            content,
        ];
    }
    return [content];
}
x6_1.Graph.registerNode('vue-shape', {
    view: 'vue-shape-view',
    markup: getMarkup(),
    attrs: {
        body: {
            fill: 'none',
            stroke: 'none',
            refWidth: '100%',
            refHeight: '100%',
        },
        fo: {
            refWidth: '100%',
            refHeight: '100%',
        },
    },
    propHooks(metadata) {
        if (metadata.markup == null) {
            const primer = metadata.primer;
            if (primer) {
                metadata.markup = getMarkup(primer);
                let attrs = {};
                switch (primer) {
                    case 'circle':
                        attrs = {
                            refCx: '50%',
                            refCy: '50%',
                            refR: '50%',
                        };
                        break;
                    case 'ellipse':
                        attrs = {
                            refCx: '50%',
                            refCy: '50%',
                            refRx: '50%',
                            refRy: '50%',
                        };
                        break;
                    default:
                        break;
                }
                metadata.attrs = x6_1.ObjectExt.merge({}, {
                    body: Object.assign({ refWidth: null, refHeight: null }, attrs),
                }, metadata.attrs || {});
            }
        }
        return metadata;
    },
}, true);
//# sourceMappingURL=node.js.map