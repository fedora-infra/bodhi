$(function() {
    $('.onlyjs').css('visibility', 'visible');
    $('.onlyjs').css('display', 'block');

    $('.hidejs').css('visibility', 'hidden');
    $('.hidejs').css('display', 'none');

    $('.rowjs').addClass('row');

    for (i = 0; i <= 12; i++)
        $('.remove-cols').removeClass('col-md-' + i);

    for (i = 0; i <= 12; i++)
        $('.js-md-' + i).addClass('col-md-' + i);
});
