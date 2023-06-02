'use strict';

function selectall(source) {
    var checkboxes = document.getElementsByTagNameNS('*', 'input');
    for(var i=0, n=checkboxes.length;i<n;i++) {
      checkboxes[i].checked = source.checked;
    }
}