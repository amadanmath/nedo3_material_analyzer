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

    let collectionReady = Promise.reject();
    let resolveCollectionReady = () => 0;
    function spanAndAttributeTypesLoaded () {
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
        let dbName = norm[0], dbKey = norm[1];
        comment += ( '<hr/>' +
                      '<a class="comment_id" href="https://uts.nlm.nih.gov//metathesaurus.html?cui=' + dbKey + '" target="uts_nlm_nih_gov">' +
                      'UMLS:' +
                      Util.escapeHTML(dbKey) + '</a>');
        let cuiName = currentDocData.cui_data[dbKey];
        if (cuiName) {
          comment += ('<br/><div>' + Util.escapeHTML(cuiName) + '</div>');
        }
      });

      displayComment(evt, target, comment, commentText, commentType);
    }

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
      .on('resize', onResize)
      .on('hideComment', hideComment)
      .on('displaySpanComment', displaySpanComment)
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
    const ws = new WebSocket(
      'ws://' +
      window.location.host +
      '/ws/brat/'
    );
    const sendJson = data => ws.send(JSON.stringify(data));


    // STATE VARIABLES
    let currentUser = null;
    let currentCount = 0;
    let listChanged = false;


    // HELPER FUNCTIONS
    function updateBadge() {
      $("#new_count")
      .text(currentCount || (listChanged ? 0 : ""))
      .removeClass('badge-light badge-secondary')
      .addClass(listChanged ? 'badge-light' : 'badge-secondary');
    }


    // PAGE ROUTING
    page({
      hashbang: true,
      dispatch: false,
    });
    page('/', ctx => {
      $('#login_page').show();
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
      sendJson({
        type: "show",
        id: ctx.params.id,
      });
    });

    // WEBSOCKET ACTIONS
    const wsActions = {
      hello: ({ user, count }) => {
        if (user) {
          $('#login_message')
          .text('Logged in')
          .removeClass().addClass('text-success');
          currentUser = user;
          currentCount = count;
          updateBadge();
          $('.logged-in').show();
          page('/input');
        } else {
          $('#login_message')
          .text('Please log in')
          .removeClass();
          currentUser = null;
          currentCount = 0;
          updateBadge();
          $('.logged-in').hide();
          page('/');
        }
      },
      loginFailed: () => {
        $('#login_message')
        .text('Login failed, please try again')
        .removeClass().addClass('text-danger');
        currentUser = null;
        currentCount = 0;
        updateBadge();
        $('.logged-in').hide();
        page('/');
      },
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
            const pos = abbrevdText.lastIndexOf(' ');
            if (pos == -1) pos = abbrevdText.length - 1;
            abbrevdText = abbrevdText.substring(0, pos) + "\u2026";
          }
          let $state;
          let stateString = DATA.states[item.state];
          if (item.state === "F") {
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
            $('<td>').text(abbrevdText)
          )
          .append(
            $('<td>').text(DATA.workers[item.action])
          )
          .append(
            $state
          )
          .append(
            $('<td>').text(new Date(item.started_at * 1000))
          )
          .appendTo($tbody);
        }
        $listPage.find('.nav-first, .nav-prev').prop('disabled', !prev);
        $listPage.find('.nav-next, .nav-last').prop('disabled', !next);
        $listPage.find('.nav-curr a').text(`${curr} / ${maxpage}`);
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
    };

    ws.onmessage = function(evt) {
      const data = JSON.parse(evt.data);
      console.log("RECEIVED:", data);
      wsActions[data.type](data);
    };

    ws.onclose = function(evt) {
      console.error('WebSocket closed unexpectedly');
    };

    // ws.onopen = function(evt) {
    // }

    $('#login_form').submit(evt => {
      sendJson({
        "type": "login",
        "username": $('#login_username').val(),
        "password": $('#login_password').val(),
      });
      $('#login_password').val('');
      evt.preventDefault();
    });

    $('#input_form').submit(evt => {
      evt.preventDefault();
    });
    $('#input_form button').click(evt => {
      console.log( {
        "type": "analyze",
        "action": $(evt.target).val(),
        "text": $('#input_text').val(),
      });
      sendJson({
        "type": "analyze",
        "action": $(evt.target).val(),
        "text": $('#input_text').val(),
      });
    });

    $('#list_button').click(evt => {
      page('/list/1');
      return false;
    });

    $('#list_page').on('click', '.show-link', evt => {
      const id = $(evt.target).closest('tr').data('id');
      page(`/show/${id}`);
      return false;
    });


  }
})();


