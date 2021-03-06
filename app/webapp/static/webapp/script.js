(() => {
  const MAX_LENGTH = 50;

  const DATA = JSON.parse(document.getElementById('data').textContent);


  head.js(
    urls.jquery,
    () => head.js(...urls.libraries, onReady)
  );


  function onReady() {

    // BRAT VARS
    const commentDisplayDelay = 0;
    const commentFadeIn = 0;
    const commentFadeOut = 0;
    let visualizer, dispatcher;
    let disabled_types = {};
    const colls = {};
    let currentDocData, currentEntities, currentNormalizations, currentColl;
    let commentFollows = true;
    let isMac = true; // TODO
    const modKey = isMac ? 'metaKey' : 'ctrlKey';
    const modKeyName = isMac ? 'Cmd' : 'Ctrl';
    let csrfToken = $('input[name="csrfmiddlewaretoken"]').val();

    let resizerTimeout = null;
    let displayCommentTimeout = null;
    let commentDisplayed = false;
    const $commentPopup = $('#commentpopup');

    const $toggles = $('#toggles_list');
    const $window = $(window);
    const $all = $('#all_toggles');

    const cursor = { x: 0, y: 0 };

    function prepareEntityToggles(coll) {
      // TODO fix
      disabled_types = {};
      $toggles.empty();

      coll.entity_types.forEach(({name, labels}) => {
        if (!labels) return; // utility type

        disabled_types[name] = false;

        const $label = $('<label>')
        .appendTo($toggles);

        $('<input type="checkbox">')
        .appendTo($label)
        .prop('checked', true)
        .click(evt => {
          let enabled = evt.target.checked;
          disabled_types[name] = !enabled;

          let values = Object.values(disabled_types);
          if (values.every(v => !v)) {
            $all.prop({
              checked: true,
              indeterminate: false,
            });
          } else if (values.every(v => v)) {
            $all.prop({
              checked: false,
              indeterminate: false,
            });
          } else {
            $all.prop({
              checked: false,
              indeterminate: true,
            });
          }

          if ($('#svg').is(':visible')) renderCurrentData();
        });

        $('<span>')
        .text(labels[0] || name)
        .appendTo($label);
      });
    }

    let collectionReady = Promise.resolve();
    let resolveCollectionReady = () => 0;
    let spanTypes = null;
    let relationTypesHash = null;
    let data = null;
    function spanAndAttributeTypesLoaded (_spanTypes, _entityAttributeTypes, _eventAttributeTypes, _relationTypesHash) {
      spanTypes = _spanTypes;
      relationTypesHash = _relationTypesHash;
      resolveCollectionReady();
    }
    function loadColl(coll, action) {
      if (colls[action] !== coll) {
        currentColl = colls[action] = coll;
        prepareEntityToggles(coll);
        collectionReady = new Promise((resolve, reject) => resolveCollectionReady = resolve);
        dispatcher.post('collectionLoaded', [coll]);
      }
    }

    function loadDoc(doc) {
      collectionReady.then(() => {
        currentDocData = doc;
        currentEntities = currentDocData.entities;

        currentNormalizations = {};
        currentDocData.normalizations.forEach(norm => currentNormalizations[norm[0]] = norm);
        $('#download-txt').removeClass('d-none').attr('href', datalink(currentDocData.text));
        $('#download-ann').removeClass('d-none').attr('href', datalink(currentDocData.annfile));
        renderCurrentData();
      });
    }

    function displayComment(evt, target, comment, commentText, commentType) {
      let classes = [];
      if (commentType) {
        // label comment by type, with special case for default note type
        let commentLabel;
        if (commentType == 'AnnotatorNotes') {
          commentLabel = '<b>Note:</b> ';
        } else {
          commentLabel = '<b>'+Util.escapeHTML(commentType)+':</b> ';
        }
        comment += commentLabel + Util.escapeHTMLwithNewlines(commentText);
        classes.push('comment_' + commentType);
      }
      if (!commentFollows) {
        classes.push('fixed-comment');
      }
      $commentPopup[0].className = classes.join(' ');
      $commentPopup.html(comment);
      adjustToCursor(evt, $commentPopup, 10, true, true);
      clearTimeout(displayCommentTimeout);
      /* slight "tooltip" delay to allow highlights to be seen
          before the popup obstructs them. */
      displayCommentTimeout = setTimeout(function() {
        $commentPopup.stop(true, true).fadeIn(commentFadeIn);
        commentDisplayed = true;
      }, commentDisplayDelay);
    }

    function adjustToCursor(evt, $element, offset, top, right) {
      if (evt) {
        cursor.x = evt.clientX;
        cursor.y = evt.clientY;
      }
      // get the real width, without wrapping
      $element.css({ left: 0, top: 0 });
      const screenHeight = $window.height();
      const screenWidth = $window.width();
      // FIXME why the hell is this 22 necessary?!?
      const elementHeight = $element.height() + 22;
      const elementWidth = $element.width() + 22;
      let x, y;
      offset = offset || 0;
      if (top) {
        y = cursor.y - elementHeight - offset;
        if (y < 0) top = false;
      }
      if (!top) {
        y = cursor.y + offset;
      }
      if (right) {
        x = cursor.x + offset;
        if (x >= screenWidth - elementWidth) right = false;
      }
      if (!right) {
        x = cursor.x - elementWidth - offset;
      }
      if (y < 0) y = 0;
      if (x < 0) x = 0;
      $element.css({ top: y, left: x });
    };

    function hideComment() {
      if (!commentFollows) return;
      clearTimeout(displayCommentTimeout);
      if (commentDisplayed) {
        $commentPopup.stop(true, true).fadeOut(commentFadeOut, function() { commentDisplayed = false; });
      }
    }

    function onMouseMove(evt) {
      if (commentDisplayed && commentFollows) {
        adjustToCursor(evt, $commentPopup, 10, true, true);
      }
    }

    function displaySpanComment(
        evt, target, spanId, spanType, mods, spanText, commentText,
        commentType, normalizations) {

      if (!commentFollows) return;

      let comment = ( '<div><span class="comment_type_id_wrapper">' +
                      '<span class="comment_type">' +
                      Util.escapeHTML(Util.spanDisplayForm(currentColl.entity_types,
                                                            spanType)) +
                      '</span>' +
                      ' ' +
                      '<span class="comment_id">' +
                      'ID:'+Util.escapeHTML(spanId) +
                      '</span></span>' );
      if (mods.length) {
        comment += '<div>' + Util.escapeHTML(mods.join(', ')) + '</div>';
      }

      comment += '</div>';
      comment += ('<div class="comment_text">"' +
                  Util.escapeHTML(spanText) +
                  '"</div>');
      $.each(normalizations, function(normNo, norm) {
        console.log(norm, currentDocData); // DEBUG
        const dbName = norm[0], dbKey = norm[1], normText = norm[2];
        const urlPattern = currentDocData.norm_urls[dbKey];
        comment += "<hr/>";
        const normCode = Util.escapeHTML(dbName + ":" + dbKey);
        if (urlPattern) {
          const url = urlPattern.replace("%s", dbKey);
          comment += '<a class="comment_id" href="' + url +
            '" target="brat_norm">' + normCode + '</a>';
        } else {
          comment += '<div class="comment_id">' + normCode + '</div>';
        }
        if (normText) {
          comment += ('<div class="norm_info_value">' + Util.escapeHTML(normText) + '</div>');
        }
      });

      displayComment(evt, target, comment, commentText, commentType);
    }

    function displayArcComment(
        evt, target, symmetric, arcId,
        originSpanId, originSpanType, role, 
        targetSpanId, targetSpanType,
        commentText, commentType) {
      var arcRole = target.attr('data-arc-role');
      // in arrowStr, &#8212 == mdash, &#8594 == Unicode right arrow
      const arrowStr = symmetric ? '&#8212;' : '&#8594;';
      const arcDisplayForm = Util.arcDisplayForm(spanTypes, 
                                                 data.spans[originSpanId].type, 
                                                 arcRole,
                                                 relationTypesHash);
      let comment = "";
      comment += ('<span class="comment_type_id_wrapper">' +
                  '<span class="comment_type">' +
                  Util.escapeHTML(Util.spanDisplayForm(spanTypes,
                                                        originSpanType)) +
                  ' ' + arrowStr + ' ' +
                  Util.escapeHTML(arcDisplayForm) +
                  ' ' + arrowStr + ' ' +
                  Util.escapeHTML(Util.spanDisplayForm(spanTypes,
                                                        targetSpanType)) +
                  '</span>' +
                  '<span class="comment_id">' +
                  (arcId ? 'ID:'+arcId : 
                    Util.escapeHTML(originSpanId) +
                    arrowStr + 
                    Util.escapeHTML(targetSpanId)) +
                  '</span>' +
                  '</span>');
      comment += ('<div class="comment_text">' + 
                  Util.escapeHTML('"'+data.spans[originSpanId].text+'"') +
                  arrowStr +
                  Util.escapeHTML('"'+data.spans[targetSpanId].text + '"') +
                  '</div>');
      displayComment(evt, target, comment, commentText, commentType);
    };

    function rememberData(_data) {
      if (_data && !_data.exception) {
        data = _data;
      }
    };



    function renderCurrentData() {
      $('#btn_cancel').prop('disabled', false);

      currentDocData.entities = currentEntities.filter(([id, name, spans]) => !disabled_types[name]);
      dispatcher.post('renderData', [currentDocData]);
    }

    function datalink(text) {
      return "data:text/plain," + text;
    }

    function resizeFunction(evt) {
      dispatcher.post('renderData');
    }

    function onResize(evt) {
      if (evt.target === window) {
        clearTimeout(resizerTimeout);
        resizerTimeout = setTimeout(resizeFunction, 100); // TODO is 100ms okay?
      }
    }

    function onSVGClicked(evt) {
      const $target = $(evt.target);
      const spanId = $target.data('span-id');
      if (spanId && commentFollows) {
        $commentPopup.addClass('fixed-comment');
        commentFollows = false;
      } else {
        $commentPopup.removeClass('fixed-comment');
        commentFollows = true;
        hideComment();
      }
    }


    // BRAT INIT
    Util.loadFonts = function() {};
    window.Configuration = {
      "abbrevsOn": true,
      "textBackgrounds": "striped",
      "visual": {
        "margin": {
          "x": 2,
          "y": 1
        },
        "arcTextMargin": 1,
        "boxSpacing": 1,
        "curlyHeight": 4,
        "arcSpacing": 9,
        "arcStartHeight": 19
      },
      "svgWidth": "100%",
      // "rapidModeOn": false,
      // "confirmModeOn": true,
      // "autorefreshOn": false,
      "typeCollapseLimit": 30
    };
    dispatcher = new Dispatcher();
    visualizer = new Visualizer(dispatcher, 'svg');
    dispatcher.post('init');

    dispatcher
      .on('spanAndAttributeTypesLoaded', spanAndAttributeTypesLoaded)
      .on('dataReady', rememberData)
      .on('resize', onResize)
      .on('hideComment', hideComment)
      .on('displaySpanComment', displaySpanComment)
      .on('displayArcComment', displayArcComment)
      .on('click', onSVGClicked)
      .on('mousemove', onMouseMove);


    $all.click(evt => {
      let enabled = evt.target.checked;
      $('#toggles_list input').prop('checked', enabled);
      Object.keys(disabled_types).forEach(k => disabled_types[k] = !enabled);

      if ($('#svg').is(':visible')) renderCurrentData();
    });

    $('#settings-opener').click(evt => {
      $('#settings-opener, #toggles').toggleClass('open');
      evt.stopPropagation();
      evt.preventDefault();
    });

    $(document).click(evt => {
      if (!$('#toggles').hasClass('open') || $(evt.target).is('#toggles, #toggles *')) return;
      $('#settings-opener, #toggles').removeClass('open');
    });


    // WEBSOCKET INIT
    const ws_protocol = location.protocol.replace('http', 'ws');
    const ws_url = (ws_protocol + "//" + location.host + location.pathname).replace(/\/$/, '') + "/ws/brat/";
    let sendJson = null;
    const WS = {
      disconnect: () => Promise.resolve(),
      connect: function connectWS() {
        return new Promise((resolve, reject) => {
          const ws = new WebSocket(ws_url);

          ws.onopen = function(evt) {
            console.log("Connected.")
            resolve();
          }

          ws.onmessage = function(evt) {
            const data = JSON.parse(evt.data);
            console.log("RECEIVED:", data);
            wsActions[data.type](data);
          };

          ws.onclose = function(evt) {
            console.log("Disconnected. Reconnecting...");
            WS.connect();
          };

          sendJson = data => ws.send(JSON.stringify(data));
          this.disconnect = function() {
            sendJson = null;
            delete ws.onclose;
            ws.close();
            return Promise.resolve();
          }
        });
      }
    }


    // STATE VARIABLES
    let currentUser = DATA.user;
    let currentCount = DATA.count;
    let shownJob = null;
    let listChanged = currentUser && currentCount;


    // HELPER FUNCTIONS
    function updateBadge() {
      $("#new_count")
      .text(currentCount || (listChanged ? 0 : ""))
      .removeClass('badge-light badge-secondary')
      .addClass(listChanged ? 'badge-light' : 'badge-secondary');
    }

    function formatDateTime(date) {
      const y = date.getFullYear();
      const m = (date.getMonth() + 1).toString().padStart(2, '0');
      const d = date.getDate().toString().padStart(2, '0');
      const h = date.getHours().toString().padStart(2, '0');
      const i = date.getMinutes().toString().padStart(2, '0');
      const s = date.getSeconds().toString().padStart(2, '0');
      return `${y}-${m}-${d} ${h}:${i}:${s}`;
    }

    function formatDuration(duration) {
      // const l = duration % 1;
      duration = Math.trunc(duration);
      const s = duration % 60;
      duration = (duration - s) / 60;
      const i = duration % 60;
      duration = (duration - i) / 60;
      const h = duration;
      let time = `${i.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
      if (h) time = `${h}:${time}`;
      return time;
    }

    function invokeDiff(ann) {
      sendJson({
        type: "diff",
        id: shownJob,
        ann,
      });
    }

    function logInOut(user, count, message, kind, skipWS) {
      $('#login_message')
      .text(message)
      .removeClass().addClass(`text-${kind}`);
      currentUser = user;
      (skipWS ? Promise.resolve() :
        user ? WS.connect() : WS.disconnect())
      .then(() => {
        currentCount = count;
        updateBadge();
        $('.logged-in').toggle(!!user);
        page('/input');
      });
    }


    // PAGE ROUTING
    console.log(DATA);
    if (DATA.subdomain) {
      page.base(DATA.subdomain);
      console.log(page.base());
    }
    page('*', (ctx, next) => { // DEBUG
      console.log("PAGE", ctx);
      next();
    });
    page({
      hashbang: true,
      dispatch: false,
    });
    page('/', ctx => {
      if (currentUser) {
        page('/input');
      } else {
        $('main > section').hide();
        $('#login_page').show();
        if ($('#login_username').val()) {
          $('#login_password').focus();
        } else {
          $('#login_username').focus();
        }
      }
    });
    page('*', (ctx, next) => {
      $('main > section').hide();
      if (currentUser) {
        next();
      } else {
        page('/');
      }
    });
    page('/input', ctx => {
      $('#input_page').show();
    });
    page('/list/:page', ctx => {
      // TODO show spinner
      sendJson({
        type: "list",
        page: ctx.params.page,
      });
    });
    page('/show/:id', ctx => {
      shownJob = ctx.params.id;
      sendJson({
        type: "show",
        id: shownJob,
      });
    });


    // WEBSOCKET ACTIONS
    const wsActions = {
      changed: ({ id, state }) => {
        console.log("changed:", id, state); // TODO REMOVE
        listChanged = true;
        if (state === "F") {
          currentCount++;
        }
        updateBadge();
      },
      viewed: ({ id }) => {
        currentCount--;
        updateBadge();
      },
      list: ({ prev, curr, next, maxpage, data }) => {
        const $listPage = $('#list_page');
        const $tbody = $listPage.find('tbody').empty();
        listChanged = false;
        updateBadge();
        for (const item of data) {
          let abbrevdText = item.txt;
          if (abbrevdText.length > MAX_LENGTH) {
            abbrevdText = abbrevdText.substring(0, MAX_LENGTH - 2);
            let pos = abbrevdText.lastIndexOf(' ');
            if (pos == -1) pos = abbrevdText.length - 1;
            abbrevdText = abbrevdText.substring(0, pos) + "\u2026";
          }
          let $state;
          let stateString = DATA.states[item.state];
          let formattedDuration = '';
          if (item.state === "F") {
            const duration = new Date(item.finished_at * 1000) - new Date(item.started_at * 1000);
            formattedDuration = formatDuration(duration / 1000);
            const $link = $('<a href="#" class="show-link">')
            .append(
              $('<span>').text(stateString)
            );
            if (!item.viewed) {
              $('<span class="badge badge-secondary">').text('New').appendTo($link.append(" "));
            }
            $state = $('<td>').append($link);
          } else {
            $state = $('<td>').text(stateString);
          }
          const $tr = $('<tr>')
          .data('id', item.id)
          .append(
            $('<td class="text_column">')
            .text(abbrevdText)
            .data("fulltext", item.txt)
          )
          .append(
            $('<td>').text(DATA.workers[item.action])
          )
          .append(
            $state
          )
          .append(
            $('<td>').text(formatDateTime(new Date(item.submitted_at * 1000)))
          )
          .append(
            $('<td>').text(formattedDuration)
          )
          .appendTo($tbody);
        }
        $listPage.find('.nav-first').attr('data-page', prev && 1).toggleClass('disabled', !prev);
        $listPage.find('.nav-prev').attr('data-page', prev).toggleClass('disabled', !prev);
        $listPage.find('.nav-next').attr('data-page', next).toggleClass('disabled', !next);
        $listPage.find('.nav-last').attr('data-page', next && maxpage).toggleClass('disabled', !next);
        $listPage.find('.nav-curr > div').text(`${curr} / ${maxpage}`);
        listCurrentPage = page;
        $listPage.show();
      },
      show: ({ action, txt, ann, doc, coll, error }) => {
        if (error) {
          console.error(error); // TODO
        } else {
          $('#show_page').show();
          loadColl(coll, action);
          loadDoc(doc)
        }
      },
      unauthorized: () => {
        logInOut(null, 0, "Session timed out; please log in again", "warning");
      },
    };


    $('#login_form').submit(evt => {
      const formData = new FormData();
      formData.append("username", $('#login_username').val());
      formData.append("password", $('#login_password').val());
      formData.append("csrfmiddlewaretoken", csrfToken);
      fetch(urls.login, {
        method: "POST",
        body: formData,
      })
      .then(response => response.json())
      .then(({ success, user, count, csrf_token }) => {
        if (success) {
          csrfToken = csrf_token;
          logInOut(user, count, `Logged in as ${user}`, "success");
        } else {
          logInOut(user, count, "Login failed; please try again", "danger");
        }
      });
      $('#login_password').val('').focus();
      evt.preventDefault();
    });

    $('#logout_button').click(evt => {
      const formData = new FormData();
      formData.append("csrfmiddlewaretoken", csrfToken);
      fetch(urls.logout, {
        method: "POST",
        body: formData,
      })
      .then(response => response.json())
      .then(data => {
        csrfToken = data.csrf_token;
        logInOut(null, 0, "Logged out; please log in again", "warning");
      });
    });

    // PROCESSING
    $('#input_form').submit(evt => {
      evt.preventDefault();
    });
    $('#input_form button').click(evt => {
      const $input_text = $('#input_text');
      sendJson({
        "type": "analyze",
        "action": $(evt.target).val(),
        "text": $input_text.val(),
      });
      $input_text.val('');
      page('/list/1');
    });

    $('#list_button').click(evt => {
      page('/list/1');
      return false;
    });

    $('#new_button').click(evt => {
      page('/input');
      return false;
    });

    $('#list_page').on('click', '.show-link', evt => {
      const id = $(evt.target).closest('tr').data('id');
      page(`/show/${id}`);
      return false;
    });

    $('#list_page').on('click', '.text_column', evt => {
      const text = $(evt.target).data('fulltext');
      $('#input_text').val(text);
      page('/input');
    });

    $('#list_page .pagination').on('click', '.page-item[data-page]', evt => {
      const nextPage = $(evt.target).closest('.page-item').attr('data-page');
      page(`/list/${nextPage}`);
    });

    $('html, #diff_upload')
    .on('dragenter dragleave dragover drop', evt => {
      evt.preventDefault();
      evt.stopPropagation();
    });
    $('html')
    .on('dragenter dragover', evt => {
      evt.originalEvent.dataTransfer.dropEffect = 'none';
    });
    $('#diff_upload')
    .on('dragenter dragover', evt => {
      evt.originalEvent.dataTransfer.dropEffect = 'copy';
      $('#diff_upload').addClass('dropping');
    })
    .on('dragleave drop', evt => {
      $('#diff_upload').removeClass('dropping');
    })
    .on('drop', evt => {
      const files = evt.originalEvent.dataTransfer.files;
      if (files.length) {
        const file = files[0];
        if (file.type.startsWith('text/')) {
          file.text().then(ann => invokeDiff(ann));
        }
      } else {
        const ann = evt.originalEvent.dataTransfer.getData('text');
        invokeDiff(ann);
      }
    })
    .on('keypress', evt => {
      if (!(evt.ctrlKey || evt.metaKey)) {
        evt.preventDefault();
        evt.stopPropagation();
      }
    })
    .on('paste', evt => {
      const ann = evt.originalEvent.clipboardData.getData('text');
      invokeDiff(ann);
      evt.preventDefault();
      evt.stopPropagation();
    });

    (currentUser ? WS.connect() : Promise.resolve())
    .then(() => {
      if (currentUser) {
        logInOut(currentUser, currentCount, `Logged in as ${currentUser}`, "success", true);
      } else {
        logInOut(currentUser, currentCount, "Please log in", "warning", true);
      }
    });
  }
})();
